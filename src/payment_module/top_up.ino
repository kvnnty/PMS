#include <SPI.h>
#include <MFRC522.h>

#define SS_PIN 10
#define RST_PIN 9

MFRC522 rfid(SS_PIN, RST_PIN);
MFRC522::Uid savedUid;

String plateNumber = "";
String balance = "";

void setup()
{
  Serial.begin(9600);
  SPI.begin();
  rfid.PCD_Init();
  Serial.println("Place your RFID card to read...");

  waitForCard();
  savedUid = rfid.uid;

  printCurrentCardData();

  if (shouldUpdate())
  {
    getUserInput();
    updateCardData();
    printUpdatedCardData();
  }
  else
  {
    Serial.println("No update performed. Exiting...");
  }

  endRFIDSession();
}

void loop()
{
  // Intentionally left empty
}

// =======================
// Core Functional Blocks
// =======================

void waitForCard()
{
  while (!rfid.PICC_IsNewCardPresent() || !rfid.PICC_ReadCardSerial())
  {
    delay(100);
  }
}

void printCurrentCardData()
{
  String currentPlate = readBlockAsString(2);
  String currentBalance = readBlockAsString(4);

  Serial.println("📄 Current RFID data:");
  Serial.print("Plate Number: ");
  Serial.println(currentPlate);
  Serial.print("Balance     : ");
  Serial.println(currentBalance);
}

bool shouldUpdate()
{
  Serial.println("Do you want to update this data? (y/n)");
  while (!Serial.available())
    ;
  char decision = tolower(Serial.read());
  return decision == 'y';
}

void getUserInput()
{
  Serial.println("Enter new plate number (max 16 chars):");
  plateNumber = getSerialInput();

  Serial.println("Enter new balance (max 16 chars):");
  balance = getSerialInput();

  Serial.print("New Plate   : ");
  Serial.println(plateNumber);
  Serial.print("New Balance : ");
  Serial.println(balance);
}

String getSerialInput()
{
  String input = "";
  while (input.length() == 0)
  {
    if (Serial.available())
    {
      input = Serial.readStringUntil('\n');
      input.trim();
      if (input.length() > 16)
        input = input.substring(0, 16);
    }
  }
  return input;
}

void updateCardData()
{
  if (writeBlock(2, plateNumber.c_str()))
  {
    Serial.println("✅ Plate number updated.");
  }
  else
  {
    Serial.println("❌ Failed to write plate number.");
  }

  if (writeBlock(4, balance.c_str()))
  {
    Serial.println("✅ Balance updated.");
  }
  else
  {
    Serial.println("❌ Failed to write balance.");
  }
}

void printUpdatedCardData()
{
  Serial.println("🔁 Re-reading updated data...");
  Serial.print("Plate Number: ");
  Serial.println(readBlockAsString(2));
  Serial.print("Balance     : ");
  Serial.println(readBlockAsString(4));
}

void endRFIDSession()
{
  rfid.PICC_HaltA();
  rfid.PCD_StopCrypto1();
}

// =======================
// RFID Read/Write Helpers
// =======================

bool writeBlock(byte blockNum, const char *data)
{
  byte buffer[16] = {0};
  strncpy((char *)buffer, data, 16);

  MFRC522::MIFARE_Key key;
  for (byte i = 0; i < 6; i++)
    key.keyByte[i] = 0xFF;

  if (!authenticate(blockNum, &key))
    return false;

  MFRC522::StatusCode status = rfid.MIFARE_Write(blockNum, buffer, 16);
  if (status != MFRC522::STATUS_OK)
  {
    Serial.print("Write failed for block ");
    Serial.println(blockNum);
    return false;
  }

  return true;
}

String readBlockAsString(byte blockNum)
{
  byte buffer[18];
  byte size = sizeof(buffer);
  String result = "";

  MFRC522::MIFARE_Key key;
  for (byte i = 0; i < 6; i++)
    key.keyByte[i] = 0xFF;

  if (!authenticate(blockNum, &key))
    return "[Auth Failed]";

  MFRC522::StatusCode status = rfid.MIFARE_Read(blockNum, buffer, &size);
  if (status != MFRC522::STATUS_OK)
  {
    Serial.print("Read failed for block ");
    Serial.println(blockNum);
    return "[Read Failed]";
  }

  for (int i = 0; i < 16 && buffer[i] != 0; i++)
  {
    result += (char)buffer[i];
  }

  return result;
}

bool authenticate(byte blockNum, MFRC522::MIFARE_Key *key)
{
  MFRC522::StatusCode status = rfid.PCD_Authenticate(
      MFRC522::PICC_CMD_MF_AUTH_KEY_A, blockNum, key, &savedUid);
  if (status != MFRC522::STATUS_OK)
  {
    Serial.print("Auth failed for block ");
    Serial.println(blockNum);
    return false;
  }
  return true;
}
