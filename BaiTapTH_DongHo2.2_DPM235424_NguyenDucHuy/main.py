import network
import ubinascii
from machine import Pin, PWM, unique_id
from time import sleep_ms, ticks_ms, ticks_diff
from umqtt.simple import MQTTClient

# ================= CẤU HÌNH =================
WIFI_SSID = "Wokwi-GUEST"
WIFI_PASS = ""

BROKER = "broker.hivemq.com"
PORT = 1883

NHOM = "minh2026abc"
TOPIC_TIME = ("dongho6servo/" + NHOM + "/time").encode()
TOPIC_STATUS = ("dongho6servo/" + NHOM + "/status").encode()
CLIENT_ID = "sub-" + NHOM + "-" + ubinascii.hexlify(unique_id()).decode()

TIMEOUT_MS = 10000      # quá 10s không nhận được dữ liệu -> coi là không hoạt động -> số 12

# (chân servo A, chân servo B, số vạch)
CHAN = {
    "gio":  (13, 12, 12),
    "phut": (14, 27, 60),
    "giay": (26, 25, 60),
}


# ================= SERVO =================
class Servo:
    def __init__(self, pin):
        self.pwm = PWM(Pin(pin), freq=50)
        self.goc = None

    def quay(self, goc):
        goc = max(0, min(180, goc))
        if self.goc is not None and abs(goc - self.goc) < 1:
            return
        duty = int(1638 + (goc / 180) * (8192 - 1638))   # 0.5ms..2.5ms
        self.pwm.duty_u16(duty)
        self.goc = goc


class Kim:
    """Một kim = 2 servo. A: nửa phải (12->6), B: nửa trái (6->12)."""
    def __init__(self, pin_a, pin_b, so_vach):
        self.A = Servo(pin_a)
        self.B = Servo(pin_b)
        self.so_vach = so_vach
        self.chi_so_12()

    def chi_so_12(self):
        self.A.quay(0)          # A: 0°   = số 12
        self.B.quay(180)        # B: 180° = số 12

    def dat_vach(self, vach):
        vach = vach % self.so_vach
        theta = vach * 360 / self.so_vach
        if theta <= 180:
            self.A.quay(theta)
            self.B.quay(180)
        else:
            self.B.quay(theta - 180)
            self.A.quay(0)


gio = Kim(*CHAN["gio"])
phut = Kim(*CHAN["phut"])
giay = Kim(*CHAN["giay"])


def ve_so_12():
    for kim in (gio, phut, giay):
        kim.chi_so_12()


# ================= XỬ LÝ TIN NHẮN MQTT =================
pub_offline = True      # ESP32 biến trở đang offline?
lan_cuoi = ticks_ms()   # lần cuối nhận dữ liệu thời gian


def nhan_tin(topic, msg):
    global pub_offline, lan_cuoi

    if topic == TOPIC_STATUS:
        if msg == b"offline":
            pub_offline = True
            ve_so_12()
            print("ESP32 bien tro OFFLINE -> ve so 12")
        else:
            pub_offline = False
            print("ESP32 bien tro ONLINE")
        return

    if topic == TOPIC_TIME:
        if pub_offline:
            return
        try:
            h, m, s = [int(x) for x in msg.decode().split(",")]
        except Exception:
            print("Du lieu loi:", msg)
            return
        lan_cuoi = ticks_ms()
        gio.dat_vach(h)
        phut.dat_vach(m)
        giay.dat_vach(s)

        # 12:00:00 đúng -> cả 6 động cơ chỉ số 12
        if h == 0 and m == 0 and s == 0:
            ve_so_12()
        print("Nhan:", "{:02d}:{:02d}:{:02d}".format(h if h else 12, m, s))


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
    c.set_callback(nhan_tin)
    c.connect()
    c.subscribe(TOPIC_STATUS)
    c.subscribe(TOPIC_TIME)
    print("MQTT OK, dang lang nghe:", TOPIC_TIME.decode())
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
lan_cuoi = ticks_ms()
t_ping = ticks_ms()

while True:
    try:
        client.check_msg()

        now = ticks_ms()
        if ticks_diff(now, t_ping) > 10000:     # giữ kết nối (keepalive 30s)
            client.ping()
            t_ping = now

        # lâu không có dữ liệu -> hệ thống không hoạt động -> số 12
        if ticks_diff(now, lan_cuoi) > TIMEOUT_MS:
            ve_so_12()

    except OSError:
        print("Mat ket noi MQTT, dang ket noi lai...")
        ve_so_12()
        client = ket_noi_lai()

    sleep_ms(20)