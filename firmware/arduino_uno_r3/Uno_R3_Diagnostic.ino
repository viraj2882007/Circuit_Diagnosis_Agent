/*
  Board-specific Arduino Uno R3 diagnostic firmware.
  Upload manually from the Arduino IDE; the host agent never flashes it for you.

  Serial Monitor / host adapter: 115200 baud, newline-terminated commands.
  Safety:
  - Disconnect all external peripherals before upload and before pin loopback tests.
  - Never connect 5V directly to GND.
  - Connect only the jumper specified by the test currently running.
  - D0/D1 are reserved for USB serial.
  - EEPROM and flash are never written by this sketch.
  - I2C scan reports ACK addresses only; it cannot prove a device is healthy.
  - I2C_READ must only be used with a known device profile/register map.
*/

#include <Arduino.h>
#include <ctype.h>
#include <stdlib.h>
#include <string.h>
#include <Wire.h>
#include <SPI.h>

static char lineBuffer[64];
static uint8_t lineLength = 0;

void printHelp() {
  Serial.println();
  Serial.println(F("=== UNO R3 DIAGNOSTIC COMMANDS ==="));
  Serial.println(F("INFO                       Identify diagnostic firmware"));
  Serial.println(F("HELP                       Show this help"));
  Serial.println(F("LED                        Blink onboard LED (D13) 3 times"));
  Serial.println(F("PAIR <out> <in>             Test digital pins in both directions"));
  Serial.println(F("                            Example: PAIR 2 3; connect D2 to D3"));
  Serial.println(F("PWM <pwm> <in>              Check PWM toggling using a jumper"));
  Serial.println(F("                            Example: PWM 3 2; connect D3 to D2"));
  Serial.println(F("ADC A<n> LOW|HIGH           Check analog input against GND or 5V"));
  Serial.println(F("                            Example: ADC A0 LOW; connect A0 to GND"));
  Serial.println(F("I2C_SCAN                    List I2C addresses that ACK"));
  Serial.println(F("SPI_LOOPBACK                Test SPI MOSI/MISO path"));
  Serial.println(F("                            Connect D11 (MOSI) to D12 (MISO)"));
  Serial.println(F("I2C_READ <addr> <reg>       Read a register from a known I2C device"));
  Serial.println(F("D0/D1 are reserved for serial. Remove/move jumpers before each test."));
  Serial.println(F("=================================="));
  Serial.println();
}

void printInfo() {
  Serial.println(F("BOARD:ARDUINO_UNO_R3"));
  Serial.println(F("MCU:ATmega328P"));
  Serial.println(F("FIRMWARE_VERSION:2"));
  Serial.println(F("CAPABILITIES:GPIO,ADC,PWM,I2C_SCAN,SPI_LOOPBACK,LED"));
  Serial.println(F("INFO RESULT: PASS"));
}

void blinkOnboardLed() {
  pinMode(LED_BUILTIN, OUTPUT);
  for (int i = 0; i < 3; ++i) {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(250);
    digitalWrite(LED_BUILTIN, LOW);
    delay(250);
  }
  pinMode(LED_BUILTIN, INPUT);
  Serial.println(F("LED test sequence complete. Did the onboard L LED blink 3 times?"));
}

bool isDigitalTestPin(int pin) {
  return pin >= 2 && pin <= 13;
}

bool testDirection(uint8_t sourcePin, uint8_t inputPin) {
  pinMode(sourcePin, INPUT);
  digitalWrite(sourcePin, LOW);
  pinMode(inputPin, INPUT_PULLUP);
  delay(3);

  pinMode(sourcePin, OUTPUT);
  digitalWrite(sourcePin, LOW);
  delay(3);
  int lowRead = digitalRead(inputPin);

  digitalWrite(sourcePin, HIGH);
  delay(3);
  int highRead = digitalRead(inputPin);

  pinMode(sourcePin, INPUT);
  digitalWrite(sourcePin, LOW);
  pinMode(inputPin, INPUT);

  bool pass = (lowRead == LOW && highRead == HIGH);
  Serial.print(F("D")); Serial.print(sourcePin);
  Serial.print(F(" output -> D")); Serial.print(inputPin);
  Serial.print(F(" input: LOW phase read=")); Serial.print(lowRead);
  Serial.print(F(", HIGH phase read=")); Serial.print(highRead);
  Serial.print(F(" => ")); Serial.println(pass ? F("PASS") : F("FAIL"));
  return pass;
}

void testPair(int firstPin, int secondPin) {
  if (!isDigitalTestPin(firstPin) || !isDigitalTestPin(secondPin) || firstPin == secondPin) {
    Serial.println(F("ERROR: Use two different digital pins from D2 through D13."));
    return;
  }

  Serial.print(F("Testing jumper connection D")); Serial.print(firstPin);
  Serial.print(F(" <-> D")); Serial.println(secondPin);
  bool forward = testDirection((uint8_t)firstPin, (uint8_t)secondPin);
  bool reverse = testDirection((uint8_t)secondPin, (uint8_t)firstPin);
  Serial.print(F("PAIR RESULT: "));
  Serial.println((forward && reverse) ? F("PASS") : F("FAIL - check jumper and pins"));
  Serial.println(F("Remove/move the jumper before the next test."));
}

bool isPwmPin(int pin) {
  return pin == 3 || pin == 5 || pin == 6 || pin == 9 || pin == 10 || pin == 11;
}

void testPwm(int pwmPin, int inputPin) {
  if (!isPwmPin(pwmPin)) {
    Serial.println(F("ERROR: PWM pin must be one of D3, D5, D6, D9, D10, D11."));
    return;
  }
  if (!isDigitalTestPin(inputPin) || pwmPin == inputPin) {
    Serial.println(F("ERROR: Input pin must be a different pin from D2 through D13."));
    return;
  }

  Serial.print(F("Testing PWM D")); Serial.print(pwmPin);
  Serial.print(F(" -> input D")); Serial.println(inputPin);
  pinMode(pwmPin, OUTPUT);
  pinMode(inputPin, INPUT);
  analogWrite(pwmPin, 128);
  delay(20);

  unsigned long highSamples = 0;
  unsigned long lowSamples = 0;
  const unsigned long sampleCount = 25000;
  for (unsigned long i = 0; i < sampleCount; ++i) {
    if (digitalRead(inputPin) == HIGH) ++highSamples;
    else ++lowSamples;
  }

  analogWrite(pwmPin, 0);
  digitalWrite(pwmPin, LOW);
  pinMode(pwmPin, INPUT);
  pinMode(inputPin, INPUT);

  Serial.print(F("Samples: HIGH=")); Serial.print(highSamples);
  Serial.print(F(" LOW=")); Serial.println(lowSamples);
  bool pass = highSamples > 20 && lowSamples > 20;
  Serial.print(F("PWM RESULT: "));
  Serial.println(pass ? F("PASS - both HIGH and LOW levels observed") :
                        F("FAIL - jumper, pin or PWM output needs checking"));
  Serial.println(F("This is a basic functional check, not a precision frequency/duty-cycle measurement."));
}

int parseAnalogPin(const char *arg) {
  if (arg == NULL || (arg[0] != 'A' && arg[0] != 'a')) return -1;
  if (arg[1] < '0' || arg[1] > '5' || arg[2] != '\0') return -1;
  return A0 + (arg[1] - '0');
}

void testAdc(const char *pinArg, const char *expectedArg) {
  int analogPin = parseAnalogPin(pinArg);
  if (analogPin < A0 || analogPin > A5) {
    Serial.println(F("ERROR: Analog pin must be A0 through A5."));
    return;
  }

  bool expectLow;
  if (strcmp(expectedArg, "LOW") == 0) expectLow = true;
  else if (strcmp(expectedArg, "HIGH") == 0) expectLow = false;
  else {
    Serial.println(F("ERROR: Expected level must be LOW or HIGH."));
    return;
  }

  pinMode(analogPin, INPUT);
  long total = 0;
  for (int i = 0; i < 16; ++i) {
    total += analogRead(analogPin);
    delay(2);
  }
  int value = (int)(total / 16);
  bool pass = expectLow ? (value <= 20) : (value >= 1000);

  Serial.print(F("ADC ")); Serial.print(pinArg);
  Serial.print(F(" expected ")); Serial.print(expectedArg);
  Serial.print(F("; average analogRead=")); Serial.print(value);
  Serial.print(F(" / 1023 => "));
  Serial.println(pass ? F("PASS") : F("FAIL - check wiring and voltage"));
}

void scanI2cBus() {
  Wire.begin();
  Wire.setClock(100000);
  int found = 0;
  for (uint8_t address = 1; address < 127; ++address) {
    Wire.beginTransmission(address);
    uint8_t error = Wire.endTransmission();
    if (error == 0) {
      Serial.print(F("I2C_ADDR:0x"));
      if (address < 16) Serial.print('0');
      Serial.println(address, HEX);
      ++found;
    }
  }
  Serial.print(F("I2C_SCAN RESULT: "));
  if (found == 0) {
    Serial.println(F("NO_DEVICES_FOUND"));
  } else {
    Serial.print(found);
    Serial.println(F(" ADDRESS(ES) ACKNOWLEDGED; DEVICE HEALTH NOT VERIFIED"));
  }
}

void readI2cRegister(int address, int reg) {
  if (address < 0x08 || address > 0x77 || reg < 0 || reg > 0xFF) {
    Serial.println(F("ERROR: I2C address must be 0x08..0x77 and register 0..255."));
    return;
  }
  Wire.begin();
  Wire.setClock(100000);
  Wire.beginTransmission((uint8_t)address);
  Wire.write((uint8_t)reg);
  uint8_t error = Wire.endTransmission(false);
  if (error != 0) {
    Serial.println(F("I2C_READ RESULT: NO_ACK"));
    return;
  }
  uint8_t count = Wire.requestFrom((uint8_t)address, (uint8_t)1);
  if (count == 1 && Wire.available()) {
    uint8_t value = Wire.read();
    Serial.print(F("I2C_READ RESULT: ADDRESS=0x"));
    Serial.print(address, HEX);
    Serial.print(F(" REGISTER=0x"));
    Serial.print(reg, HEX);
    Serial.print(F(" VALUE=0x"));
    Serial.println(value, HEX);
  } else {
    Serial.println(F("I2C_READ RESULT: NO_DATA"));
  }
}

void testSpiLoopback() {
  Serial.println(F("SPI loopback: connect D11 MOSI to D12 MISO; disconnect external SPI devices."));
  pinMode(10, OUTPUT);
  digitalWrite(10, HIGH);
  SPI.begin();
  SPI.beginTransaction(SPISettings(250000, MSBFIRST, SPI_MODE0));
  const uint8_t values[] = {0x55, 0xAA, 0x00, 0xFF, 0x96};
  bool pass = true;
  for (size_t i = 0; i < sizeof(values); ++i) {
    uint8_t received = SPI.transfer(values[i]);
    if (received != values[i]) pass = false;
    Serial.print(F("SPI sent 0x"));
    Serial.print(values[i], HEX);
    Serial.print(F(" received 0x"));
    Serial.println(received, HEX);
  }
  SPI.endTransaction();
  SPI.end();
  pinMode(10, INPUT);
  Serial.print(F("SPI_LOOPBACK RESULT: "));
  Serial.println(pass ? F("PASS") : F("FAIL - check D11/D12 jumper and pins"));
}

void processLine(char *line) {
  while (*line && isspace((unsigned char)*line)) ++line;
  for (char *p = line; *p; ++p) *p = (char)toupper((unsigned char)*p);
  if (*line == '\0') return;

  char command[16] = {0};
  char arg1[16] = {0};
  char arg2[16] = {0};
  int count = sscanf(line, "%15s %15s %15s", command, arg1, arg2);

  if (strcmp(command, "INFO") == 0) {
    printInfo();
  } else if (strcmp(command, "HELP") == 0) {
    printHelp();
  } else if (strcmp(command, "LED") == 0) {
    blinkOnboardLed();
  } else if (strcmp(command, "PAIR") == 0 && count == 3) {
    testPair(atoi(arg1), atoi(arg2));
  } else if (strcmp(command, "PWM") == 0 && count == 3) {
    testPwm(atoi(arg1), atoi(arg2));
  } else if (strcmp(command, "ADC") == 0 && count == 3) {
    testAdc(arg1, arg2);
  } else if (strcmp(command, "I2C_SCAN") == 0) {
    scanI2cBus();
  } else if (strcmp(command, "SPI_LOOPBACK") == 0) {
    testSpiLoopback();
  } else if (strcmp(command, "I2C_READ") == 0 && count == 3) {
    readI2cRegister((int)strtol(arg1, NULL, 0), (int)strtol(arg2, NULL, 0));
  } else {
    Serial.println(F("ERROR: Unknown/incomplete command. Type HELP."));
  }
}

void setup() {
  pinMode(LED_BUILTIN, INPUT);
  Serial.begin(115200);
  unsigned long start = millis();
  while (!Serial && millis() - start < 3000) { }
  Serial.println();
  Serial.println(F("UNO R3 DIAGNOSTIC SKETCH READY"));
  printInfo();
  Serial.println(F("No external wires should be connected until a test asks for one."));
  printHelp();
  blinkOnboardLed();
}

void loop() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      lineBuffer[lineLength] = '\0';
      processLine(lineBuffer);
      lineLength = 0;
    } else if (lineLength < sizeof(lineBuffer) - 1) {
      lineBuffer[lineLength++] = c;
    } else {
      lineLength = 0;
      Serial.println(F("ERROR: command too long; type HELP."));
    }
  }
}
