#include <SPI.h>
#include <MFRC522.h>

#define RST_PIN    9       
#define SS_PIN    10   

MFRC522 mfrc522(SS_PIN, RST_PIN);  

// Add connection verification
void setup() {
    Serial.begin(9600);     
    while (!Serial);        
    SPI.begin();
    mfrc522.PCD_Init();     
    delay(100);
    
    // Test communication
    byte version = mfrc522.PCD_ReadRegister(mfrc522.VersionReg);
    Serial.print(F("MFRC522 Software Version: 0x"));
    Serial.print(version, HEX);
    if (version == 0x91 || version == 0x92) {
        Serial.println(F(" = v1.0 or v2.0"));
    } else if (version == 0x12) {
        Serial.println(F(" = counterfeit chip"));
    } else {
        Serial.println(F(" = (unknown - check connections)"));
    }
    
    Serial.println(F("DISPLAYING UID, SAK, TYPE, AND DATA BLOCKS:"));
}
void loop(){
    if(!mfrc522.PICC_IsNewCardPresent()){
        return;
    }

    if(!mfrc522.PICC_ReadCardSerial()){
        return;
    }

    // Show basic card info
    Serial.print(F("Card UID:"));
    for (byte i = 0; i < mfrc522.uid.size; i++) {
        Serial.print(mfrc522.uid.uidByte[i] < 0x10 ? " 0" : " ");
        Serial.print(mfrc522.uid.uidByte[i], HEX);
    }
    Serial.println();
    
    // Try reading just sector 0 first
    if (readSector0()) {
        Serial.println(F("Sector 0 read successfully"));
        // Only try full dump if sector 0 works
        mfrc522.PICC_DumpToSerial(&(mfrc522.uid));
    } else {
        Serial.println(F("Cannot read card - communication error"));
    }
    
    mfrc522.PICC_HaltA();
    mfrc522.PCD_StopCrypto1();
    delay(2000);
}

bool readSector0() {
    MFRC522::MIFARE_Key key;
    for (byte i = 0; i < 6; i++) {
        key.keyByte[i] = 0xFF;
    }
    
    MFRC522::StatusCode status = mfrc522.PCD_Authenticate(
        MFRC522::PICC_CMD_MF_AUTH_KEY_A, 0, &key, &(mfrc522.uid));
    
    if (status != MFRC522::STATUS_OK) {
        Serial.print(F("Auth failed: "));
        Serial.println(mfrc522.GetStatusCodeName(status));
        return false;
    }
    return true;
}