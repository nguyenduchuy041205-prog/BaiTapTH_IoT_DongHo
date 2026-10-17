from machine import Pin, PWM, ADC
from time import sleep_ms

# ---------- Cấu hình phần cứng ----------
# (chân biến trở, chân servo A, chân servo B, số vạch trên mặt đồng hồ)
HANDS = {
    "gio":  (34, 13, 12, 12),   # 12 vạch giờ  -> mỗi vạch 30°
    "phut": (35, 14, 27, 60),   # 60 vạch phút -> mỗi vạch 6°
    "giay": (32, 26, 25, 60),   # 60 vạch giây -> mỗi vạch 6°
}

ADC_MAX = 4095          # ADC 12-bit của ESP32
NGUONG_LOI = 15         # đọc dưới ngưỡng này coi như không hoạt động -> số 12


# ---------- Điều khiển servo ----------
class Servo:
    def __init__(self, pin):
        self.pwm = PWM(Pin(pin), freq=50)
        self.goc = None

    def quay(self, goc):
        goc = max(0, min(180, goc))
        if self.goc is not None and abs(goc - self.goc) < 1:
            return                          # tránh rung servo
        # xung 0.5ms..2.5ms trong chu kỳ 20ms (duty_u16: 1638..8192)
        duty = int(1638 + (goc / 180) * (8192 - 1638))
        self.pwm.duty_u16(duty)
        self.goc = goc


# ---------- Một kim = một cặp servo ----------
class Kim:
    def __init__(self, pin_adc, pin_a, pin_b, so_vach):
        self.adc = ADC(Pin(pin_adc))
        self.adc.atten(ADC.ATTN_11DB)       # đo đến ~3.3V
        self.A = Servo(pin_a)               # nửa phải: 12 -> 6
        self.B = Servo(pin_b)               # nửa trái: 6 -> 12
        self.so_vach = so_vach
        self.chi_so_12()

    def chi_so_12(self):
        self.A.quay(0)                      # A: 0°   = số 12
        self.B.quay(180)                    # B: 180° = số 12

    def doc_gia_tri(self):
        """Trung bình 8 lần đọc; trả None nếu biến trở lỗi."""
        try:
            tong = 0
            for _ in range(8):
                tong += self.adc.read()
            gt = tong // 8
        except Exception:
            return None
        if gt < NGUONG_LOI:
            return None                     # không hoạt động
        return gt

    def cap_nhat(self):
        gt = self.doc_gia_tri()
        if gt is None:
            self.chi_so_12()
            return 0

        vach = int(gt * self.so_vach / (ADC_MAX + 1))   # 0 .. so_vach-1
        theta = vach * 360 / self.so_vach               # góc trên mặt đồng hồ

        if theta <= 180:                    # nửa phải: servo A làm việc
            self.A.quay(theta)
            self.B.quay(180)                # B đỗ ở số 12
        else:                               # nửa trái: servo B làm việc
            self.B.quay(theta - 180)
            self.A.quay(0)                  # A đỗ ở số 12
        return vach


# ---------- Chương trình chính ----------
gio  = Kim(*HANDS["gio"])
phut = Kim(*HANDS["phut"])
giay = Kim(*HANDS["giay"])

while True:
    h = gio.cap_nhat()
    m = phut.cap_nhat()
    s = giay.cap_nhat()

    # 12:00:00 đúng -> cả 6 động cơ chỉ số 12
    if h == 0 and m == 0 and s == 0:
        for kim in (gio, phut, giay):
            kim.chi_so_12()

    print("Thoi gian: {:02d}:{:02d}:{:02d}".format(h if h else 12, m, s))
    sleep_ms(100)