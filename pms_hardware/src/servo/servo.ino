// Code 7
#include <Servo.h>
// Code 1
Servo barrierServo;
// Code 3
#define TRIGGER_PIN 2
#define ECHO_PIN 3
#define RED_LED_PIN 4
#define BLUE_LED_PIN 5
#define SERVO_PIN 6
#define GND_PIN_1 7
#define GND_PIN_2 8
#define BUZZER_PIN 12
// Code 2
bool gateOpen = false;
unsigned long lastBuzzTime = 0;
const unsigned long buzzInterval = 300;
bool buzzerState = false;
void initializeSerial() {
  Serial.begin(9600);
}
void initializeUltrasonic() {
  pinMode(TRIGGER_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
}
// Code 4
void testIndicators() {
  digitalWrite(BLUE_LED_PIN, HIGH);
  digitalWrite(BUZZER_PIN, HIGH);
  delay(500);
  digitalWrite(BLUE_LED_PIN, LOW);
  digitalWrite(BUZZER_PIN, LOW);
  digitalWrite(RED_LED_PIN, HIGH);
}
// Code 5
void handleSerialCommands() {
  if (Serial.available()) {
    char cmd = Serial.read();
    if (cmd == '1') openGate();
    else if (cmd == '0') closeGate();
  }
}
// Code 6
float measureDistance() {
  digitalWrite(TRIGGER_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIGGER_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIGGER_PIN, LOW);
  long duration = pulseIn(ECHO_PIN, HIGH);
  return (duration * 0.0343) / 2.0;
}
// Code 8
void setGatePosition(int angle) {
  barrierServo.write(angle);
}
void openGate() {
  setGatePosition(90);
  gateOpen = true;
  digitalWrite(BLUE_LED_PIN, HIGH);
  digitalWrite(RED_LED_PIN, LOW);
}
void closeGate() {
  setGatePosition(6);
  gateOpen = false;
  digitalWrite(BLUE_LED_PIN, LOW);
  digitalWrite(RED_LED_PIN, HIGH);
  digitalWrite(BUZZER_PIN, LOW);
}
// Code 9
void loop() {
  float distance = measureDistance();
  Serial.println(distance);
  handleSerialCommands();
  handleBuzzer();
  delay(50);
}
// Code 10
void handleBuzzer() {
  if (gateOpen) {
    unsigned long currentMillis = millis();
    if (currentMillis - lastBuzzTime >= buzzInterval) {
      buzzerState = !buzzerState;
      digitalWrite(BUZZER_PIN, buzzerState);
      lastBuzzTime = currentMillis;
    }
  }
}
// Additional setup functions (implied from the exam)
void initializeLEDs() {
  pinMode(RED_LED_PIN, OUTPUT);
  pinMode(BLUE_LED_PIN, OUTPUT);
}
void initializeBuzzer() {
  pinMode(BUZZER_PIN, OUTPUT);
}
void initializeHardcodedGrounds() {
  pinMode(GND_PIN_1, OUTPUT);
  pinMode(GND_PIN_2, OUTPUT);
  digitalWrite(GND_PIN_1, LOW);
  digitalWrite(GND_PIN_2, LOW);
}
void initializeServo() {
  barrierServo.attach(SERVO_PIN);
  setGatePosition(6);
}
void setup() {
  initializeSerial();
  initializeUltrasonic();
  initializeLEDs();
  initializeBuzzer();
  initializeHardcodedGrounds();
  initializeServo();
  testIndicators();
}