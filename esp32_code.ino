#include <RadioLib.h>

// ====== Радио (SX1281) пины ======
#define CS_PIN    2   // NSS_CTS
#define IRQ_PIN   27  // DIO1
#define RST_PIN   25  // NRESET
#define BUSY_PIN  26  // BUSY

SX1281 radio = new Module(CS_PIN, IRQ_PIN, RST_PIN, BUSY_PIN);

// ====== UART2 (поменяй пины если нужно) ======
#define UART2_RX_PIN 16
#define UART2_TX_PIN 17
#define UART2_BAUD   115200

String uart2Buf = "";

void setup() {
  Serial.begin(115200);
  Serial.println(F("[SYS] start"));

  Serial2.begin(UART2_BAUD, SERIAL_8N1, UART2_RX_PIN, UART2_TX_PIN);
  Serial.println(F("[UART2] started"));

  Serial.print(F("[SX1281] Initializing ... "));
  int state = radio.begin();
  if (state == RADIOLIB_ERR_NONE) {
    Serial.println(F("success!"));
  } else {
    Serial.print(F("failed, code "));
    Serial.println(state);
    while (true) { delay(1000); }
  }

  Serial.println(F("[SX1281] Ready."));
}

void loop() {
  // ---------- 1) Обработка входящего с UART2, пересылка на радио ----------
  while (Serial2.available()) {
    char c = (char)Serial2.read();
    if (c == '\r') continue;
    uart2Buf += c;
    if (c == '\n' || c == 'E') {
      uart2Buf.trim();
      if (uart2Buf.length() > 0) {
        Serial.print(F("[UART2 -> RADIO] Sending: "));
        Serial.println(uart2Buf);
        int txState = radio.transmit(uart2Buf);
        if (txState == RADIOLIB_ERR_NONE) {
          Serial.println(F("[RADIO TX] success"));
        } else {
          Serial.print(F("[RADIO TX] failed, code "));
          Serial.println(txState);
        }
      }
      uart2Buf = "";
    }
  }

  // ---------- 2) Приём с радио — ищем все S...E и отправляем по UART2 с добавлением ;dBm перед E ----------
  String rxData;
  // Таймаут при receive — подбери под своё приложение (здесь 500 ms)
  int rxState = radio.receive(rxData, 500);

  if (rxState == RADIOLIB_ERR_NONE) {
    rxData.trim();
    Serial.print(F("[RADIO RX] raw: "));
    Serial.println(rxData);

    // Получим RSSI для принятого пакета (будем использовать для всех найденных S..E)
    float rssi_f = radio.getRSSI();
    int rssi_int = (int)rssi_f; // целое dBm

    int start = rxData.indexOf('S');
    while (start >= 0) {
      int end = rxData.indexOf('E', start + 1);
      if (end < 0) break; // нет завершающей E — выходим

      String packet = rxData.substring(start, end + 1); // S...E включительно

      // Лог
      Serial.print(F("[RADIO] Found S..E: "));
      Serial.println(packet);

      // Вставляем ;<dBm> прямо перед конечной 'E'
      if (packet.length() >= 2) {
        String withoutE = packet.substring(0, packet.length() - 1); // без 'E'
        String out = withoutE + ";" + String(rssi_int) + "E";

        // Отправляем по UART2 без перевода строки
        Serial.print(F("[RADIO -> UART2] sending with dBm: "));
        Serial.println(out);
        Serial2.print(out); // <-- НЕТ '\n' в конце, как просили
      } else {
        Serial.println(F("[RADIO] Packet too short, ignored."));
      }

      // продолжаем искать следующий S после текущего end
      start = rxData.indexOf('S', end + 1);
    }

  } else if (rxState == RADIOLIB_ERR_RX_TIMEOUT) {
    // нормально — пакетов не было
  } else {
    Serial.print(F("[RADIO RX] error code "));
    Serial.println(rxState);
  }

  delay(10);
}
