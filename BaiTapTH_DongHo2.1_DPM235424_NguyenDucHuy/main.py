import network
import ubinascii
from machine import Pin, ADC, unique_id
from time import sleep_ms, ticks_ms, ticks_diff
from umqtt.simple import MQTTClient

WIFI_SSID = "Wokwi-GUEST"       # WiFi giả lập của Wokwi
WIFI_PASS = ""

BROKER = "broker.hivemq.com"    # HiveMQ public broker
PORT = 1883


NHOM = "minh2026abc"
TOPIC_TIME = ("dongho6servo/" + NHOM + "/time").encode()
TOPIC_STATUS = ("dongho6servo/" + NHOM + "/status").encode()
CLIENT_ID = "pub-" + NHOM + "-" + ubinascii.hexlify(unique_id()).decode()

ADC_MAX = 4095
NGUONG_LOI = 15                 # đọc dưới ngưỡng này = biến trở không hoạt động
GUI_LAI_MS = 2000               # gửi lại định kỳ (heartbeat) để bên nhận biết còn sống


# ================= BIẾN TRỞ =================
class BienTro:
    def __init__(self, pin, so_vach):
        self.adc = ADC(Pin(pin))
        self.adc.atten(ADC.ATTN_11DB)
        self.so_vach = so_vach

    def doc(self):
        """Trả về vạch 0..so_vach-1 (0 = số 12). Biến trở lỗi -> 0."""
        try:
            tong = 0
            for _ in range(8):
                tong += self.adc.read()
            gt = tong // 8
        except Exception:
            return 0
        if gt < NGUONG_LOI:
            return 0
        return int(gt * self.so_vach / (ADC_MAX + 1))


gio = BienTro(34, 12)           # 12 vạch giờ
phut = BienTro(35, 60)          # 60 vạch phút
giay = BienTro(32, 60)          # 60 vạch giây


# ================= WIFI + MQTT =================
def ket_noi_wifi():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if not wlan.isconnected():
        print("Dang ket noi WiFi", end="")
        wlan.connect(WIFI_SSID, WIFI_PASS)
        while not wlan.isconnected():
            print(".", end="")
            sleep_ms(200)
    print("\nWiFi OK:", wlan.ifconfig()[0])


def ket_noi_mqtt():
    c = MQTTClient(CLIENT_ID, BROKER, port=PORT, keepalive=30)
    # Nếu ESP32 này mất kết nối đột ngột, broker tự báo "offline"
    c.set_last_will(TOPIC_STATUS, b"offline", retain=True)
    c.connect()
    c.publish(TOPIC_STATUS, b"online", retain=True)
    print("MQTT OK:", BROKER)
    return c


def ket_noi_lai():
    while True:
        try:
            ket_noi_wifi()
            return ket_noi_mqtt()
        except OSError as e:
            print("Loi ket noi:", e, "- thu lai sau 2s")
            sleep_ms(2000)


# ================= CHƯƠNG TRÌNH CHÍNH =================
client = ket_noi_lai()
cuoi = None
t_gui = ticks_ms()

while True:
    h, m, s = gio.doc(), phut.doc(), giay.doc()
    hien_tai = (h, m, s)

    if hien_tai != cuoi or ticks_diff(ticks_ms(), t_gui) > GUI_LAI_MS:
        try:
            client.publish(TOPIC_TIME, "{},{},{}".format(h, m, s).encode(), retain=True)
            cuoi = hien_tai
            t_gui = ticks_ms()
            print("Gui:", "{:02d}:{:02d}:{:02d}".format(h if h else 12, m, s))
        except OSError:
            print("Mat ket noi MQTT, dang ket noi lai...")
            client = ket_noi_lai()

    sleep_ms(100)