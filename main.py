import json
import os
import threading
from datetime import datetime
from kivy.app import App
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.uix.image import Image
from kivy.clock import Clock, mainthread
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.core.audio import SoundLoader
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if '__file__' in locals() else os.getcwd()
LOGO_PATH = os.path.join(BASE_DIR, "kizilay.png")
DATA_FILE = os.path.join(BASE_DIR, "anket_verileri.json")
FEEDBACK_FILE = os.path.join(BASE_DIR, "geri_bildirimler.json")
HISTORY_FILE = os.path.join(BASE_DIR, "anket_gecmisi.json")
USERS_FILE = os.path.join(BASE_DIR, "uyeler.json")
VOICE_FILE = os.path.join(BASE_DIR, "ses.mp3")

# --- KURUMSAL RENK PALETİ ---
COLOR_BG_DARK = (0.06, 0.09, 0.14, 1.0)       # Derin Lacivert Arka Plan (#0F172A)
COLOR_CARD_BG = (0.11, 0.16, 0.23, 0.95)     # Kart Arka Planı (#1E293B)
COLOR_PRIMARY = (0.85, 0.12, 0.15, 1.0)     # Kızılay Kırmızısı (#D32F2F)
COLOR_SECONDARY = (0.12, 0.53, 0.90, 1.0)   # Kızılay / Engelsiz Mavi (#1E88E5)
COLOR_SUCCESS = (0.16, 0.65, 0.38, 1.0)     # Başarı Yeşili (#2E7D32)
COLOR_WARNING = (0.95, 0.60, 0.07, 1.0)     # Uyarı Sarısı (#F59E0B)
COLOR_MUTED = (0.30, 0.38, 0.47, 1.0)       # Nötr Çizgiler & Butonlar

# --- SES MOTORU (TTS & ANDROID MEDIA) ---
def clean_markup(text):
    for tag in ["[b]", "[/b]", "[color=33ccff]", "[/color]", "[color=ffbb33]", "[color=33ff33]", 
                "[color=ff4444]", "[size=12sp]", "[size=13sp]", "[size=14sp]", "[size=15sp]", "[size=16sp]", "[size=18sp]", "[/size]", 
                "🔊", "🎙️", "📝", "ℹ️", "✉️", "👥", "🚪", "🔒", "👤", "🚶", "➕", "🗑️", "🔑", "🛡️"]:
        text = text.replace(tag, "")
    return text.strip()

def play_android_media(file_path):
    try:
        from jnius import autoclass
        MediaPlayer = autoclass('android.media.MediaPlayer')
        mp = MediaPlayer()
        mp.setDataSource(file_path)
        mp.prepare()
        mp.start()
        return True
    except Exception:
        return False

def speak_text(text):
    clean_txt = clean_markup(text)
    if not clean_txt:
        return

    def _worker():
        try:
            from gtts import gTTS
            tts = gTTS(text=clean_txt, lang='tr', slow=False)
            tts.save(VOICE_FILE)
            if not play_android_media(VOICE_FILE):
                try:
                    snd = SoundLoader.load(VOICE_FILE)
                    if snd:
                        snd.play()
                except Exception:
                    pass
        except Exception:
            pass

    threading.Thread(target=_worker, daemon=True).start()


# --- MODERN KURUMSAL UI BİLEŞENLERİ ---
class ModernCard(BoxLayout):
    """Yuvarlatılmış kurumsal kart konteyneri"""
    def __init__(self, bg_color=COLOR_CARD_BG, radius=[16], **kwargs):
        super().__init__(**kwargs)
        self.bg_color = bg_color
        self.radius = radius
        with self.canvas.before:
            Color(*self.bg_color)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=self.radius)
        self.bind(pos=self._update_rect, size=self._update_rect)

    def _update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size


class ModernButton(Button):
    """Yuvarlatılmış kurumsal modern buton"""
    def __init__(self, bg_color=COLOR_PRIMARY, radius=[12], **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_color = (0, 0, 0, 0)
        self.custom_bg = bg_color
        self.radius = radius
        self.font_size = '14sp'
        self.bold = True
        with self.canvas.before:
            self.col = Color(*self.custom_bg)
            self.rect = RoundedRectangle(pos=self.pos, size=self.size, radius=self.radius)
        self.bind(pos=self._update_rect, size=self._update_rect)

    def _update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def on_press(self):
        # Basılma efekti (hafif koyulaşma)
        self.col.rgba = (self.custom_bg[0]*0.8, self.custom_bg[1]*0.8, self.custom_bg[2]*0.8, self.custom_bg[3])

    def on_release(self):
        self.col.rgba = self.custom_bg


class ModernTextInput(TextInput):
    """Kurumsal temaya uygun estetik giriş alanı"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_active = ''
        self.background_color = (0.16, 0.22, 0.31, 1.0)
        self.foreground_color = (1, 1, 1, 1)
        self.cursor_color = (0.85, 0.12, 0.15, 1)
        self.hint_text_color = (0.55, 0.65, 0.75, 1)
        self.padding = [14, 12, 14, 12]
        self.font_size = '14sp'


# --- SESLE YAZMA / DİKTE PANELİ ---
class VoiceInputDialog(Popup):
    def __init__(self, target_input, field_name="Giriş Alanı", **kwargs):
        super().__init__(**kwargs)
        self.target_input = target_input
        self.title = f"Sesli Yazma Asistanı: {field_name}"
        self.title_size = '15sp'
        self.size_hint = (0.9, 0.52)
        self.auto_dismiss = False
        self.separator_color = list(COLOR_PRIMARY)

        layout = ModernCard(orientation='vertical', padding=15, spacing=10)
        
        layout.add_widget(Label(
            text="Metin alanına dokunun ve klavyenizdeki [b]Mikrofon (🎙️)[/b] simgesiyle konuşun:",
            markup=True,
            font_size='13sp',
            halign='center',
            text_size=(290, None),
            size_hint_y=0.28
        ))

        self.voice_text_input = ModernTextInput(
            text="",
            hint_text="Söyledikleriniz buraya aktarılacak...",
            multiline=True,
            size_hint_y=0.44
        )
        layout.add_widget(self.voice_text_input)

        btn_box = BoxLayout(spacing=10, size_hint_y=0.28)
        
        btn_apply = ModernButton(text="Aktar ve Onayla", bg_color=COLOR_SUCCESS)
        btn_apply.bind(on_press=self.apply_text)
        
        btn_cancel = ModernButton(text="İptal", bg_color=COLOR_PRIMARY)
        btn_cancel.bind(on_press=self.dismiss)

        btn_box.add_widget(btn_apply)
        btn_box.add_widget(btn_cancel)
        layout.add_widget(btn_box)

        self.content = layout
        speak_text(f"{field_name} için sesli yazma paneli açıldı.")

    def apply_text(self, instance):
        spoken = self.voice_text_input.text.strip()
        if spoken:
            if self.target_input.text.strip():
                self.target_input.text += " " + spoken
            else:
                self.target_input.text = spoken
            speak_text(f"Kayıt edildi: {spoken}")
        self.dismiss()

def open_voice_input(target_input, field_name="Giriş"):
    dialog = VoiceInputDialog(target_input=target_input, field_name=field_name)
    dialog.open()


# --- VERİ YÖNETİMİ FONKSİYONLARI ---
DEFAULT_DATA = {
    "admins": {"admin": "12345"},
    "questions": [
        {
            "soru": "1. Görme engelli bir bireyle karşılaştığınızda nasıl iletişim kurarsınız?",
            "secenekler": ["Doğrudan seslenerek kendimi tanıtırım", "Kolundan tutup çekerim", "Yüksek sesle bağırırım"]
        },
        {
            "soru": "2. Bedensel engelli birine tekerlekli sandalye kullanırken nasıl yaklaşırsınız?",
            "secenekler": ["Yardım isteyip istemediğini sorarım", "İzin istemeden sandalyeyi iterim", "Görmezden gelirim"]
        },
        {
            "soru": "3. İşitme engelli bir kişiyle iletişim kurarken hangisi doğrudur?",
            "secenekler": ["Yüzüne bakarak ve net konuşurum", "Arkamı dönüp konuşurum", "Hızlıca fısıldarım"]
        },
        {
            "soru": "4. Engelli bir bireye hitap ederken hangi dil tercih edilmelidir?",
            "secenekler": ["Saygılı, eşit ve kapsayıcı dil", "Acıyıcı ve dramatik ifadeler", "Aşırı abartılı övgüler"]
        },
        {
            "soru": "5. Rehber köpek kullanan bir görme engelli gördüğümüzde ne yapmalıyız?",
            "secenekler": ["Köpeğin görevde olduğunu bilip müdahale etmem", "Köpeği sevip dikkatini dağıtırım", "Köpeğe mama veririm"]
        }
    ]
}

def load_data():
    if not os.path.exists(DATA_FILE):
        save_data(DEFAULT_DATA)
        return DEFAULT_DATA
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_DATA

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=4)

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_history(entry):
    history = load_history()
    history.append(entry)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=4)

def save_feedback(name, email, message):
    feedbacks = []
    if os.path.exists(FEEDBACK_FILE):
        try:
            with open(FEEDBACK_FILE, "r", encoding="utf-8") as f:
                feedbacks = json.load(f)
        except Exception:
            feedbacks = []
    feedbacks.append({
        "tarih": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "isim": name,
        "eposta": email,
        "mesaj": message
    })
    with open(FEEDBACK_FILE, "w", encoding="utf-8") as f:
        json.dump(feedbacks, f, ensure_ascii=False, indent=4)

def show_popup(title, message):
    speak_text(f"{title}. {message}")
    popup = Popup(
        title=title, 
        content=Label(text=message, halign="center", font_size='14sp'), 
        size_hint=(0.85, 0.4),
        separator_color=list(COLOR_PRIMARY)
    )
    popup.open()

def get_logo_widget(size_y=0.25):
    if os.path.exists(LOGO_PATH):
        return Image(source=LOGO_PATH, size_hint=(1, size_y), allow_stretch=True, keep_ratio=True)
    else:
        return Label(
            text="[b][color=ff3333]TÜRK KIZILAY[/color][/b]\n[size=13sp]ENGELSİZ VAN EDREMİT[/size]", 
            markup=True, halign='center', size_hint_y=size_y
        )


class BackgroundScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(*COLOR_BG_DARK)
            self.bg_rect = Rectangle(size=self.size, pos=self.pos)
        self.bind(size=self._update_bg, pos=self._update_bg)

    def _update_bg(self, *args):
        self.bg_rect.size = self.size
        self.bg_rect.pos = self.pos


# 1. ANA GİRİŞ SEÇİM EKRANI
class EntryChoiceScreen(BackgroundScreen):
    def on_enter(self):
        self.clear_widgets()
        root = BoxLayout(orientation='vertical', padding=[20, 25, 20, 25], spacing=12)
        
        root.add_widget(get_logo_widget(size_y=0.28))
        
        card = ModernCard(orientation='vertical', padding=15, spacing=10, size_hint_y=0.72)
        
        card.add_widget(Label(
            text="[b]ENGELSİZ YAŞAM ERİŞİMİ[/b]\n[size=12sp][color=94a3b8]Van Edremit Kızılay Engelsiz Yaşam Daire Başkanlığı[/color][/size]", 
            markup=True, halign='center', font_size='16sp', size_hint_y=0.2
        ))
        
        btn_tts = ModernButton(text="🔊 Sayfayı Sesli Dinle", bg_color=COLOR_WARNING, size_hint_y=0.18)
        btn_tts.bind(on_press=lambda x: speak_text("Engelsiz Yaşam Erişimi platformu. Seçenekler: Üye Girişi, Misafir Girişi ve Yönetici Girişi."))
        card.add_widget(btn_tts)
        
        btn_member = ModernButton(text="👤 Üye Girişi / Kayıt Ol", bg_color=COLOR_SECONDARY, size_hint_y=0.2)
        btn_member.bind(on_press=lambda x: setattr(self.manager, 'current', 'member_login_screen'))
        card.add_widget(btn_member)

        btn_guest = ModernButton(text="🚶 Misafir Girişi", bg_color=COLOR_SUCCESS, size_hint_y=0.2)
        btn_guest.bind(on_press=lambda x: setattr(self.manager, 'current', 'guest_name_screen'))
        card.add_widget(btn_guest)
        
        btn_admin = ModernButton(text="🛡️ Yönetici Girişi", bg_color=COLOR_PRIMARY, size_hint_y=0.2)
        btn_admin.bind(on_press=lambda x: setattr(self.manager, 'current', 'admin_login_screen'))
        card.add_widget(btn_admin)
        
        root.add_widget(card)
        self.add_widget(root)
        speak_text("Engelsiz Yaşam Erişimi ana ekranına hoş geldiniz.")


# 2. ÜYE GİRİŞ EKRANI
class MemberLoginScreen(BackgroundScreen):
    def on_enter(self):
        self.clear_widgets()
        root = BoxLayout(orientation='vertical', padding=20, spacing=10)
        
        root.add_widget(get_logo_widget(size_y=0.2))
        
        card = ModernCard(orientation='vertical', padding=15, spacing=8, size_hint_y=0.8)
        card.add_widget(Label(text="[b]Üye Giriş Paneli[/b]", markup=True, font_size='16sp', size_hint_y=0.1))
        
        btn_tts = ModernButton(text="🔊 Ekranı Dinle", bg_color=COLOR_WARNING, size_hint_y=0.12)
        btn_tts.bind(on_press=lambda x: speak_text("Üye Giriş Ekranı. E-posta adresinizi ve şifrenizi giriniz."))
        card.add_widget(btn_tts)
        
        box_email = BoxLayout(spacing=6, size_hint_y=0.15)
        self.email_in = ModernTextInput(hint_text="E-posta Adresi", multiline=False, size_hint_x=0.76)
        btn_mic_email = ModernButton(text="🎙️ Söyle", bg_color=COLOR_SECONDARY, size_hint_x=0.24)
        btn_mic_email.bind(on_press=lambda x: open_voice_input(self.email_in, "E-posta Adresi"))
        box_email.add_widget(self.email_in)
        box_email.add_widget(btn_mic_email)
        card.add_widget(box_email)
        
        self.pass_in = ModernTextInput(hint_text="Şifre", password=True, multiline=False, size_hint_y=0.15)
        card.add_widget(self.pass_in)
        
        btn_login = ModernButton(text="Giriş Yap", bg_color=COLOR_SECONDARY, size_hint_y=0.16)
        btn_login.bind(on_press=self.member_login)
        card.add_widget(btn_login)
        
        btn_register = ModernButton(text="Hesabın Yok mu? Kayıt Ol", bg_color=COLOR_SUCCESS, size_hint_y=0.16)
        btn_register.bind(on_press=lambda x: setattr(self.manager, 'current', 'register_screen'))
        card.add_widget(btn_register)
        
        btn_back = ModernButton(text="Geri Dön", bg_color=COLOR_MUTED, size_hint_y=0.14)
        btn_back.bind(on_press=lambda x: setattr(self.manager, 'current', 'entry_choice'))
        card.add_widget(btn_back)
        
        root.add_widget(card)
        self.add_widget(root)
        speak_text("Üye Giriş Ekranı.")

    def member_login(self, instance):
        email = self.email_in.text.strip().lower()
        password = self.pass_in.text.strip()
        users = load_users()
        
        if email in users:
            user_data = users[email]
            if user_data["password"] == password:
                if user_data.get("status") == "beklemede":
                    show_popup("Onay Bekleniyor", "Hesabınız yönetici onayı beklemektedir.")
                    return
                app = App.get_running_app()
                app.guest_name = user_data["fullname"]
                app.user_email = email
                app.user_title = user_data.get("title", "Üye / Gönüllü")
                app.user_duty = user_data.get("duty", "Henüz atanmış bir görev bulunmuyor.")
                self.manager.current = "guest_menu"
            else:
                show_popup("Hata", "Şifre hatalı!")
        else:
            show_popup("Hata", "Kayıtlı üye bulunamadı!")


# 3. YENİ ÜYE KAYIT EKRANI
class RegisterScreen(BackgroundScreen):
    def on_enter(self):
        self.clear_widgets()
        root = BoxLayout(orientation='vertical', padding=15, spacing=8)
        
        root.add_widget(get_logo_widget(size_y=0.18))
        
        card = ModernCard(orientation='vertical', padding=14, spacing=7, size_hint_y=0.82)
        card.add_widget(Label(text="[b]Gönüllü / Üye Kaydı[/b]", markup=True, font_size='16sp', size_hint_y=0.1))
        
        box_name = BoxLayout(spacing=6, size_hint_y=0.14)
        self.name_in = ModernTextInput(hint_text="Ad Soyad", multiline=False, size_hint_x=0.76)
        btn_mic_name = ModernButton(text="🎙️ Söyle", bg_color=COLOR_SECONDARY, size_hint_x=0.24)
        btn_mic_name.bind(on_press=lambda x: open_voice_input(self.name_in, "Ad Soyad"))
        box_name.add_widget(self.name_in)
        box_name.add_widget(btn_mic_name)
        card.add_widget(box_name)
        
        box_email = BoxLayout(spacing=6, size_hint_y=0.14)
        self.email_in = ModernTextInput(hint_text="E-posta Adresi", multiline=False, size_hint_x=0.76)
        btn_mic_email = ModernButton(text="🎙️ Söyle", bg_color=COLOR_SECONDARY, size_hint_x=0.24)
        btn_mic_email.bind(on_press=lambda x: open_voice_input(self.email_in, "E-posta"))
        box_email.add_widget(self.email_in)
        box_email.add_widget(btn_mic_email)
        card.add_widget(box_email)
        
        self.pass_in = ModernTextInput(hint_text="Şifre Belirleyin", password=True, multiline=False, size_hint_y=0.14)
        card.add_widget(self.pass_in)
        
        btn_save = ModernButton(text="Kaydı Tamamla (Onaya Gönder)", bg_color=COLOR_SUCCESS, size_hint_y=0.16)
        btn_save.bind(on_press=self.register_user)
        card.add_widget(btn_save)
        
        btn_back = ModernButton(text="Girişe Dön", bg_color=COLOR_MUTED, size_hint_y=0.14)
        btn_back.bind(on_press=lambda x: setattr(self.manager, 'current', 'member_login_screen'))
        card.add_widget(btn_back)
        
        root.add_widget(card)
        self.add_widget(root)
        speak_text("Yeni Üye Kayıt Ekranı.")

    def register_user(self, instance):
        name = self.name_in.text.strip()
        email = self.email_in.text.strip().lower()
        password = self.pass_in.text.strip()
        
        if not (name and email and password):
            show_popup("Uyarı", "Lütfen tüm alanları doldurunuz.")
            return
            
        users = load_users()
        if email in users:
            show_popup("Hata", "Bu e-posta adresi zaten kayıtlı.")
            return
            
        users[email] = {
            "fullname": name,
            "password": password,
            "title": "Üye / Gönüllü",
            "duty": "Henüz atanmış bir görev bulunmuyor.",
            "status": "beklemede",
            "created_at": datetime.now().strftime("%d/%m/%Y %H:%M")
        }
        save_users(users)
        show_popup("Başarılı", "Kaydınız alındı! Yönetici onayından sonra giriş yapabilirsiniz.")
        self.manager.current = "member_login_screen"


# 4. MİSAFİR GİRİŞ EKRANI
class GuestNameScreen(BackgroundScreen):
    def on_enter(self):
        self.clear_widgets()
        root = BoxLayout(orientation='vertical', padding=20, spacing=10)
        
        root.add_widget(get_logo_widget(size_y=0.22))
        
        card = ModernCard(orientation='vertical', padding=15, spacing=10, size_hint_y=0.78)
        card.add_widget(Label(
            text="[b]Misafir Girişi[/b]\n[size=12sp][color=94a3b8]Lütfen Adınızı ve Soyadınızı Giriniz[/color][/size]", 
            markup=True, halign='center', font_size='16sp', size_hint_y=0.2
        ))
        
        box_name = BoxLayout(spacing=6, size_hint_y=0.2)
        self.name_in = ModernTextInput(hint_text="Adınız ve Soyadınız", multiline=False, size_hint_x=0.76)
        btn_mic_name = ModernButton(text="🎙️ Söyle", bg_color=COLOR_SECONDARY, size_hint_x=0.24)
        btn_mic_name.bind(on_press=lambda x: open_voice_input(self.name_in, "Ad ve Soyad"))
        box_name.add_widget(self.name_in)
        box_name.add_widget(btn_mic_name)
        card.add_widget(box_name)
        
        btn_continue = ModernButton(text="Giriş Yap ve Menüye Geç", bg_color=COLOR_SUCCESS, size_hint_y=0.22)
        btn_continue.bind(on_press=self.proceed)
        card.add_widget(btn_continue)
        
        btn_back = ModernButton(text="Geri Dön", bg_color=COLOR_MUTED, size_hint_y=0.18)
        btn_back.bind(on_press=lambda x: setattr(self.manager, 'current', 'entry_choice'))
        card.add_widget(btn_back)
        
        root.add_widget(card)
        self.add_widget(root)
        speak_text("Misafir Girişi.")

    def proceed(self, instance):
        name = self.name_in.text.strip()
        if not name:
            show_popup("Uyarı", "Lütfen adınızı ve soyadınızı giriniz.")
            return
        app = App.get_running_app()
        app.guest_name = name
        app.user_email = ""
        app.user_title = "Misafir Katılımcı"
        app.user_duty = "Anket Doldurma ve Farkındalık Katılımı"
        self.manager.current = "guest_menu"


# 5. KULLANICI / MİSAFİR MENÜSÜ
class GuestMenuScreen(BackgroundScreen):
    def on_enter(self):
        self.clear_widgets()
        app = App.get_running_app()
        root = BoxLayout(orientation='vertical', padding=15, spacing=8)
        
        root.add_widget(get_logo_widget(size_y=0.15))
        
        card_user = ModernCard(orientation='vertical', padding=10, spacing=3, size_hint_y=0.22, bg_color=(0.14, 0.20, 0.29, 0.95))
        card_user.add_widget(Label(text=f"[b]{app.guest_name}[/b]", markup=True, font_size='16sp', halign='center'))
        card_user.add_widget(Label(text=f"[color=38bdf8]Unvan:[/color] {app.user_title}", markup=True, font_size='13sp', halign='center'))
        card_user.add_widget(Label(text=f"[color=fbbf24]Görev:[/color] {app.user_duty}", markup=True, font_size='12sp', halign='center', text_size=(310, None)))
        root.add_widget(card_user)
        
        card_menu = ModernCard(orientation='vertical', padding=12, spacing=7, size_hint_y=0.63)
        
        btn_tts = ModernButton(text="🔊 Menüyü Sesli Oku", bg_color=COLOR_WARNING, size_hint_y=0.16)
        btn_tts.bind(on_press=lambda x: speak_text(f"Hoş geldiniz {app.guest_name}. Unvanınız: {app.user_title}. Göreviniz: {app.user_duty}. Seçenekler: Ankete Katıl, Hakkımızda, İletişim Formu, Emeği Geçenler."))
        card_menu.add_widget(btn_tts)
        
        btn_survey = ModernButton(text="📝 Ankete Katıl", bg_color=COLOR_SUCCESS, size_hint_y=0.18)
        btn_survey.bind(on_press=lambda x: setattr(self.manager, 'current', 'survey_screen'))
        card_menu.add_widget(btn_survey)
        
        btn_about = ModernButton(text="ℹ️ Hakkımızda", bg_color=COLOR_SECONDARY, size_hint_y=0.16)
        btn_about.bind(on_press=lambda x: setattr(self.manager, 'current', 'about_screen'))
        card_menu.add_widget(btn_about)
        
        btn_feedback = ModernButton(text="✉️ İletişim & Geri Bildirim Formu", bg_color=COLOR_MUTED, size_hint_y=0.16)
        btn_feedback.bind(on_press=lambda x: setattr(self.manager, 'current', 'feedback_screen'))
        card_menu.add_widget(btn_feedback)
        
        btn_credits = ModernButton(text="👥 Emeği Geçenler & Geliştirici", bg_color=(0.4, 0.3, 0.55, 1), size_hint_y=0.16)
        btn_credits.bind(on_press=lambda x: setattr(self.manager, 'current', 'credits_screen'))
        card_menu.add_widget(btn_credits)
        
        btn_logout = ModernButton(text="🚪 Çıkış Yap", bg_color=COLOR_PRIMARY, size_hint_y=0.14)
        btn_logout.bind(on_press=lambda x: setattr(self.manager, 'current', 'entry_choice'))
        card_menu.add_widget(btn_logout)
        
        root.add_widget(card_menu)
        self.add_widget(root)
        speak_text(f"Hoş geldiniz {app.guest_name}.")


# 6. YÖNETİCİ GİRİŞ EKRANI
class AdminLoginScreen(BackgroundScreen):
    def on_enter(self):
        self.clear_widgets()
        root = BoxLayout(orientation='vertical', padding=20, spacing=10)
        
        root.add_widget(get_logo_widget(size_y=0.2))
        
        card = ModernCard(orientation='vertical', padding=15, spacing=10, size_hint_y=0.78)
        card.add_widget(Label(text="[b]Yönetici Kontrol Girişi[/b]", markup=True, font_size='17sp', size_hint_y=0.15))
        
        box_u = BoxLayout(spacing=6, size_hint_y=0.18)
        self.u_in = ModernTextInput(hint_text="Kullanıcı Adı", multiline=False, size_hint_x=0.76)
        btn_mic = ModernButton(text="🎙️ Söyle", bg_color=COLOR_SECONDARY, size_hint_x=0.24)
        btn_mic.bind(on_press=lambda x: open_voice_input(self.u_in, "Yönetici Adı"))
        box_u.add_widget(self.u_in)
        box_u.add_widget(btn_mic)
        card.add_widget(box_u)
        
        self.p_in = ModernTextInput(hint_text="Şifre", password=True, multiline=False, size_hint_y=0.18)
        card.add_widget(self.p_in)
        
        btn_login = ModernButton(text="Giriş Yap", bg_color=COLOR_PRIMARY, size_hint_y=0.2)
        btn_login.bind(on_press=self.admin_login)
        card.add_widget(btn_login)
        
        btn_back = ModernButton(text="Geri Dön", bg_color=COLOR_MUTED, size_hint_y=0.15)
        btn_back.bind(on_press=lambda x: setattr(self.manager, 'current', 'entry_choice'))
        card.add_widget(btn_back)
        
        root.add_widget(card)
        self.add_widget(root)
        speak_text("Yönetici Giriş Paneli.")

    def admin_login(self, instance):
        u = self.u_in.text.strip()
        p = self.p_in.text.strip()
        data = load_data()
        admins = data.get("admins", {})
        
        if u == "aklıselimteam" and p == "Anka2026":
            app = App.get_running_app()
            app.is_super_admin = True
            app.current_admin_user = u
            self.manager.current = "admin_panel"
        elif u in admins and admins[u] == p:
            app = App.get_running_app()
            app.is_super_admin = False
            app.current_admin_user = u
            self.manager.current = "admin_panel"
        else:
            show_popup("Hata", "Geçersiz yönetici bilgileri!")


# 7. YÖNETİCİ PANELİ
class AdminPanel(BackgroundScreen):
    def on_enter(self):
        self.clear_widgets()
        app = App.get_running_app()
        users = load_users()
        pending_count = sum(1 for u in users.values() if u.get("status") == "beklemede")
        
        root = BoxLayout(orientation='vertical', padding=15, spacing=8)
        
        title_card = ModernCard(orientation='vertical', padding=10, size_hint_y=0.14, bg_color=(0.14, 0.20, 0.29, 0.95))
        title_card.add_widget(Label(
            text=f"[b]YÖNETİCİ KONTROL MERKEZİ[/b]\n[size=12sp][color=38bdf8]Aktif: {app.current_admin_user}[/color][/size]", 
            markup=True, halign='center', font_size='16sp'
        ))
        root.add_widget(title_card)
        
        card = ModernCard(orientation='vertical', padding=12, spacing=7, size_hint_y=0.86)
        
        badge = f" [color=ff4444]({pending_count} Onay Bekliyor)[/color]" if pending_count > 0 else ""
        btn_users = ModernButton(text=f"👥 Üye & Görev Yönetimi{badge}", markup=True, bg_color=COLOR_SECONDARY, size_hint_y=0.14)
        btn_users.bind(on_press=lambda x: setattr(self.manager, 'current', 'member_management_screen'))
        card.add_widget(btn_users)

        btn_stats = ModernButton(text="📊 Anket Sayısı ve Tarihçesi", bg_color=(0.15, 0.6, 0.6, 1), size_hint_y=0.14)
        btn_stats.bind(on_press=lambda x: setattr(self.manager, 'current', 'stats_screen'))
        card.add_widget(btn_stats)
        
        btn_add = ModernButton(text="➕ Yeni Soru Ekle", bg_color=COLOR_SUCCESS, size_hint_y=0.14)
        btn_add.bind(on_press=lambda x: setattr(self.manager, 'current', 'add_question_screen'))
        card.add_widget(btn_add)
        
        btn_del = ModernButton(text="🗑️ Soru Sil / Düzenle", bg_color=COLOR_PRIMARY, size_hint_y=0.14)
        btn_del.bind(on_press=lambda x: setattr(self.manager, 'current', 'delete_question_screen'))
        card.add_widget(btn_del)
        
        btn_add_admin = ModernButton(text="🔑 Yeni Yönetici Hesabı Ekle", bg_color=(0.35, 0.45, 0.7, 1), size_hint_y=0.14)
        btn_add_admin.bind(on_press=lambda x: setattr(self.manager, 'current', 'add_admin_screen'))
        card.add_widget(btn_add_admin)
        
        if not app.is_super_admin:
            btn_pass = ModernButton(text="🔒 Şifre Değiştir", bg_color=COLOR_MUTED, size_hint_y=0.14)
            btn_pass.bind(on_press=lambda x: setattr(self.manager, 'current', 'change_pass_screen'))
            card.add_widget(btn_pass)
        else:
            card.add_widget(Label(text="Sabit Süper Yönetici Şifresi Değiştirilemez", color=(0.7, 0.7, 0.7, 1), font_size='11sp', size_hint_y=0.08))
            
        btn_logout = ModernButton(text="🚪 Yönetici Çıkışı", bg_color=(0.7, 0.15, 0.15, 1), size_hint_y=0.14)
        btn_logout.bind(on_press=lambda x: setattr(self.manager, 'current', 'entry_choice'))
        card.add_widget(btn_logout)
        
        root.add_widget(card)
        self.add_widget(root)
        speak_text("Yönetici Kontrol Paneli.")


# 8. ÜYE VE GÖREV YÖNETİMİ EKRANI
class MemberManagementScreen(BackgroundScreen):
    def on_enter(self):
        self.clear_widgets()
        users = load_users()
        active_users = {k: v for k, v in users.items() if v.get("status") == "onaylandi"}
        pending_users = {k: v for k, v in users.items() if v.get("status") == "beklemede"}
        
        root = BoxLayout(orientation='vertical', padding=12, spacing=7)
        
        head_card = ModernCard(orientation='vertical', padding=8, size_hint_y=0.14, bg_color=(0.14, 0.20, 0.29, 0.95))
        head_card.add_widget(Label(
            text=f"[b]ÜYE & GÖREV YÖNETİMİ[/b]\n[size=12sp]Aktif: [color=4ade80]{len(active_users)}[/color] | Bekleyen: [color=facc15]{len(pending_users)}[/color][/size]", 
            markup=True, halign='center'
        ))
        root.add_widget(head_card)
        
        btn_add_manual = ModernButton(text="➕ Yönetici Olarak Yeni Üye Ekle", bg_color=COLOR_SUCCESS, size_hint_y=0.08)
        btn_add_manual.bind(on_press=lambda x: setattr(self.manager, 'current', 'admin_add_user_screen'))
        root.add_widget(btn_add_manual)
        
        scroll = ScrollView(size_hint=(1, 0.69))
        grid = GridLayout(cols=1, spacing=8, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        
        if pending_users:
            grid.add_widget(Label(text="[b]-- Onay Bekleyenler --[/b]", markup=True, color=(1, 0.8, 0.2, 1), size_hint_y=None, height=25))
            for email, info in pending_users.items():
                box = ModernCard(orientation='vertical', size_hint_y=None, height=75, padding=6, bg_color=(0.18, 0.24, 0.35, 1))
                box.add_widget(Label(text=f"{info['fullname']} ({email})", font_size='12sp', halign='left', text_size=(300, None)))
                
                btn_box = BoxLayout(spacing=8, size_hint_y=None, height=28)
                btn_ok = ModernButton(text="Onayla", bg_color=COLOR_SUCCESS)
                btn_ok.bind(on_press=lambda inst, e=email: self.approve_user(e))
                
                btn_reject = ModernButton(text="Reddet", bg_color=COLOR_PRIMARY)
                btn_reject.bind(on_press=lambda inst, e=email: self.delete_user(e))
                
                btn_box.add_widget(btn_ok)
                btn_box.add_widget(btn_reject)
                box.add_widget(btn_box)
                grid.add_widget(box)
                
        grid.add_widget(Label(text="[b]-- Aktif Üyeler --[/b]", markup=True, color=(0.4, 0.8, 1, 1), size_hint_y=None, height=25))
        
        if not active_users:
            grid.add_widget(Label(text="Kayıtlı aktif üye bulunmuyor.", size_hint_y=None, height=30))
        else:
            for email, info in active_users.items():
                card = ModernCard(orientation='vertical', size_hint_y=None, height=85, padding=6, bg_color=(0.14, 0.20, 0.29, 1))
                txt = f"[b]{info['fullname']}[/b] | [color=38bdf8]{info.get('title','Üye')}[/color]\nGörev: {info.get('duty','Tanımlanmamış')}"
                card.add_widget(Label(text=txt, markup=True, font_size='11sp', halign='left', text_size=(310, None), size_hint_y=0.6))
                
                btn_box = BoxLayout(spacing=8, size_hint_y=0.4)
                btn_assign = ModernButton(text="Görev Ata", bg_color=COLOR_SECONDARY)
                btn_assign.bind(on_press=lambda inst, e=email: self.open_assign_screen(e))
                
                btn_del = ModernButton(text="Üyeyi Çıkar", bg_color=COLOR_PRIMARY)
                btn_del.bind(on_press=lambda inst, e=email: self.delete_user(e))
                
                btn_box.add_widget(btn_assign)
                btn_box.add_widget(btn_del)
                card.add_widget(btn_box)
                grid.add_widget(card)
                
        scroll.add_widget(grid)
        root.add_widget(scroll)
        
        btn_back = ModernButton(text="Yönetici Paneline Dön", bg_color=COLOR_MUTED, size_hint_y=0.09)
        btn_back.bind(on_press=lambda x: setattr(self.manager, 'current', 'admin_panel'))
        root.add_widget(btn_back)
        
        self.add_widget(root)

    def approve_user(self, email):
        users = load_users()
        if email in users:
            users[email]["status"] = "onaylandi"
            save_users(users)
            show_popup("Başarılı", f"{email} üyeliği onaylandı.")
            self.on_enter()

    def delete_user(self, email):
        users = load_users()
        if email in users:
            del users[email]
            save_users(users)
            show_popup("Başarılı", f"{email} sistemden çıkarıldı.")
            self.on_enter()

    def open_assign_screen(self, email):
        app = App.get_running_app()
        app.selected_user_email = email
        self.manager.current = "assign_duty_screen"


# 9. GÖREV & UNVAN ATAMA EKRANI
class AssignDutyScreen(BackgroundScreen):
    def on_enter(self):
        self.clear_widgets()
        app = App.get_running_app()
        users = load_users()
        user_info = users.get(app.selected_user_email, {})
        
        root = BoxLayout(orientation='vertical', padding=15, spacing=8)
        card = ModernCard(orientation='vertical', padding=15, spacing=8)
        
        header = f"[b]Görev & Unvan Ataması[/b]\n[size=12sp]{user_info.get('fullname', '')} ({app.selected_user_email})[/size]"
        card.add_widget(Label(text=header, markup=True, halign='center', font_size='15sp', size_hint_y=0.14))
        
        box_t = BoxLayout(spacing=6, size_hint_y=0.14)
        self.title_in = ModernTextInput(text=user_info.get("title", "Üye / Gönüllü"), hint_text="Üye Unvanı", multiline=False, size_hint_x=0.76)
        btn_mic_t = ModernButton(text="🎙️ Söyle", bg_color=COLOR_SECONDARY, size_hint_x=0.24)
        btn_mic_t.bind(on_press=lambda x: open_voice_input(self.title_in, "Üye Unvanı"))
        box_t.add_widget(self.title_in)
        box_t.add_widget(btn_mic_t)
        card.add_widget(box_t)
        
        box_d = BoxLayout(spacing=6, size_hint_y=0.36)
        self.duty_in = ModernTextInput(text=user_info.get("duty", ""), hint_text="Görev ve Sorumluluk Talimatları...", multiline=True, size_hint_x=0.76)
        btn_mic_d = ModernButton(text="🎙️ Söyle", bg_color=COLOR_SECONDARY, size_hint_x=0.24)
        btn_mic_d.bind(on_press=lambda x: open_voice_input(self.duty_in, "Görev Açıklaması"))
        box_d.add_widget(self.duty_in)
        box_d.add_widget(btn_mic_d)
        card.add_widget(box_d)
        
        btn_save = ModernButton(text="Görevi Kaydet ve Ata", bg_color=COLOR_SUCCESS, size_hint_y=0.18)
        btn_save.bind(on_press=self.save_duty)
        card.add_widget(btn_save)
        
        btn_back = ModernButton(text="İptal / Geri Dön", bg_color=COLOR_MUTED, size_hint_y=0.14)
        btn_back.bind(on_press=lambda x: setattr(self.manager, 'current', 'member_management_screen'))
        card.add_widget(btn_back)
        
        root.add_widget(card)
        self.add_widget(root)
        speak_text("Görev ve unvan atama ekranı.")

    def save_duty(self, instance):
        app = App.get_running_app()
        users = load_users()
        if app.selected_user_email in users:
            t = self.title_in.text.strip() or "Üye / Gönüllü"
            d = self.duty_in.text.strip() or "Henüz atanmış bir görev bulunmuyor."
            users[app.selected_user_email]["title"] = t
            users[app.selected_user_email]["duty"] = d
            save_users(users)
            show_popup("Başarılı", "Üyenin unvan ve görevi güncellendi.")
            self.manager.current = "member_management_screen"


# 10. YÖNETİCİ TARAFINDAN MANUEL ÜYE EKLEME
class AdminAddUserScreen(BackgroundScreen):
    def on_enter(self):
        self.clear_widgets()
        root = BoxLayout(orientation='vertical', padding=15, spacing=8)
        card = ModernCard(orientation='vertical', padding=14, spacing=6)
        
        card.add_widget(Label(text="[b]Yönetici Tarafından Üye Ekleme[/b]", markup=True, font_size='16sp', size_hint_y=0.1))
        
        self.name_in = ModernTextInput(hint_text="Üye Adı Soyadı", multiline=False, size_hint_y=0.12)
        self.email_in = ModernTextInput(hint_text="Üye E-posta Adresi", multiline=False, size_hint_y=0.12)
        self.pass_in = ModernTextInput(hint_text="Üye Şifresi", password=True, multiline=False, size_hint_y=0.12)
        self.title_in = ModernTextInput(hint_text="Üye Unvanı", multiline=False, size_hint_y=0.12)
        self.duty_in = ModernTextInput(hint_text="Görev Sorumluluğu", multiline=False, size_hint_y=0.14)
        
        card.add_widget(self.name_in)
        card.add_widget(self.email_in)
        card.add_widget(self.pass_in)
        card.add_widget(self.title_in)
        card.add_widget(self.duty_in)
        
        btn_save = ModernButton(text="Üyeyi Onaylı Olarak Ekle", bg_color=COLOR_SUCCESS, size_hint_y=0.14)
        btn_save.bind(on_press=self.save_user)
        card.add_widget(btn_save)
        
        btn_back = ModernButton(text="Geri Dön", bg_color=COLOR_MUTED, size_hint_y=0.12)
        btn_back.bind(on_press=lambda x: setattr(self.manager, 'current', 'member_management_screen'))
        card.add_widget(btn_back)
        
        root.add_widget(card)
        self.add_widget(root)

    def save_user(self, instance):
        name = self.name_in.text.strip()
        email = self.email_in.text.strip().lower()
        password = self.pass_in.text.strip()
        title = self.title_in.text.strip() or "Üye / Gönüllü"
        duty = self.duty_in.text.strip() or "Henüz atanmış bir görev bulunmuyor."
        
        if not (name and email and password):
            show_popup("Uyarı", "Lütfen zorunlu alanları doldurunuz.")
            return
            
        users = load_users()
        if email in users:
            show_popup("Hata", "Bu e-posta zaten kayıtlı.")
            return
            
        users[email] = {
            "fullname": name,
            "password": password,
            "title": title,
            "duty": duty,
            "status": "onaylandi",
            "created_at": datetime.now().strftime("%d/%m/%Y %H:%M")
        }
        save_users(users)
        show_popup("Başarılı", "Üye başarıyla eklendi, onaylandı ve görevi atandı.")
        self.manager.current = "member_management_screen"


# 11. İSTATİSTİK VE ANKET TARİHÇESİ EKRANI
class StatsScreen(BackgroundScreen):
    def on_enter(self):
        self.clear_widgets()
        history = load_history()
        root = BoxLayout(orientation='vertical', padding=15, spacing=8)
        
        card = ModernCard(orientation='vertical', padding=12, spacing=8)
        total_count = len(history)
        card.add_widget(Label(
            text=f"[b]Anket İstatistikleri[/b]\nToplam Tamamlanan: [color=4ade80]{total_count}[/color]", 
            markup=True, halign='center', font_size='16sp', size_hint_y=0.16
        ))
        
        btn_tts = ModernButton(text="🔊 İstatistikleri Sesli Dinle", bg_color=COLOR_WARNING, size_hint_y=0.12)
        btn_tts.bind(on_press=lambda x: speak_text(f"Toplam tamamlanan anket sayısı: {total_count}."))
        card.add_widget(btn_tts)
        
        scroll = ScrollView(size_hint=(1, 0.6))
        grid = GridLayout(cols=1, spacing=6, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        
        if not history:
            grid.add_widget(Label(text="Kayıtlı anket bulunmuyor.", size_hint_y=None, height=35))
        else:
            for item in reversed(history):
                txt = f"{item['tarih']} - {item['isim']}"
                lbl = Label(text=txt, size_hint_y=None, height=30, font_size='12sp', halign="left")
                lbl.bind(size=lbl.setter('text_size'))
                grid.add_widget(lbl)
                
        scroll.add_widget(grid)
        card.add_widget(scroll)
        
        btn_back = ModernButton(text="Geri Dön", bg_color=COLOR_MUTED, size_hint_y=0.12)
        btn_back.bind(on_press=lambda x: setattr(self.manager, 'current', 'admin_panel'))
        card.add_widget(btn_back)
        
        root.add_widget(card)
        self.add_widget(root)
        speak_text(f"Anket İstatistikleri. Toplam {total_count} adet anket tamamlanmıştır.")


# 12. YENİ YÖNETİCİ HESABI EKLEME
class AddAdminScreen(BackgroundScreen):
    def on_enter(self):
        self.clear_widgets()
        root = BoxLayout(orientation='vertical', padding=20, spacing=10)
        card = ModernCard(orientation='vertical', padding=15, spacing=10)
        
        card.add_widget(Label(text="[b]Yeni Yönetici Hesabı Ekle[/b]", markup=True, font_size='17sp', size_hint_y=0.18))
        self.new_u = ModernTextInput(hint_text="Yeni Yönetici Kullanıcı Adı", multiline=False, size_hint_y=0.18)
        self.new_p = ModernTextInput(hint_text="Yeni Yönetici Şifresi", password=True, multiline=False, size_hint_y=0.18)
        card.add_widget(self.new_u)
        card.add_widget(self.new_p)
        
        btn_save = ModernButton(text="Hesabı Kaydet", bg_color=COLOR_SUCCESS, size_hint_y=0.2)
        btn_save.bind(on_press=self.save_new_admin)
        card.add_widget(btn_save)
        
        btn_back = ModernButton(text="Geri Dön", bg_color=COLOR_MUTED, size_hint_y=0.16)
        btn_back.bind(on_press=lambda x: setattr(self.manager, 'current', 'admin_panel'))
        card.add_widget(btn_back)
        
        root.add_widget(card)
        self.add_widget(root)

    def save_new_admin(self, instance):
        u = self.new_u.text.strip()
        p = self.new_p.text.strip()
        if not (u and p):
            show_popup("Uyarı", "Kullanıcı adı ve şifre boş bırakılamaz.")
            return
        if u == "aklıselimteam":
            show_popup("Hata", "Bu kullanıcı adı rezerve edilmiştir.")
            return
        data = load_data()
        if "admins" not in data:
            data["admins"] = {}
        data["admins"][u] = p
        save_data(data)
        show_popup("Başarılı", f"'{u}' adlı yeni yönetici hesabı oluşturuldu.")
        self.manager.current = "admin_panel"


# 13. ANKET EKRANI
class SurveyScreen(BackgroundScreen):
    def on_enter(self):
        self.clear_widgets()
        self.current_q = 0
        self.answers = []
        self.data = load_data()["questions"]
        self.show_question()

    def show_question(self):
        self.clear_widgets()
        if self.current_q < len(self.data) and self.current_q < 5:
            q_data = self.data[self.current_q]
            root = BoxLayout(orientation='vertical', padding=15, spacing=8)
            card = ModernCard(orientation='vertical', padding=14, spacing=9)
            
            card.add_widget(Label(text=f"[b]Soru {self.current_q + 1} / 5[/b]", markup=True, font_size='16sp', size_hint_y=0.1))
            card.add_widget(Label(text=q_data["soru"], text_size=(300, None), font_size='14sp', halign='center', size_hint_y=0.22))
            
            options_text = ", ".join([f"Seçenek {i+1}: {opt}" for i, opt in enumerate(q_data["secenekler"])])
            full_speech = f"Soru {self.current_q + 1}. {q_data['soru']}. {options_text}"
            
            btn_tts = ModernButton(text="🔊 Soruyu ve Şıkları Sesli Dinle", bg_color=COLOR_WARNING, size_hint_y=0.14)
            btn_tts.bind(on_press=lambda x: speak_text(full_speech))
            card.add_widget(btn_tts)
            
            speak_text(full_speech)
            
            for sec in q_data["secenekler"]:
                btn = ModernButton(text=sec, bg_color=COLOR_SECONDARY, size_hint_y=0.18)
                btn.bind(on_press=lambda inst, ans=sec: self.next_q(ans))
                card.add_widget(btn)
                
            root.add_widget(card)
            self.add_widget(root)
        else:
            self.finish_survey()

    def next_q(self, ans):
        speak_text(f"Cevabınız: {ans}")
        self.answers.append(ans)
        self.current_q += 1
        self.show_question()

    def finish_survey(self):
        app = App.get_running_app()
        now_str = datetime.now().strftime("%d/%m/%Y %H:%M")
        save_history({
            "isim": app.guest_name,
            "eposta": app.user_email,
            "tarih": now_str
        })
        
        speak_text("Tebrikler! Anketi başarıyla tamamladınız. Sonuçları PDF olarak indirebilirsiniz.")
        
        root = BoxLayout(orientation='vertical', padding=20, spacing=10)
        card = ModernCard(orientation='vertical', padding=20, spacing=12)
        
        card.add_widget(Label(text="[b]Anket Tamamlandı![/b]\nKatkınız ve duyarlılığınız için teşekkür ederiz.", markup=True, halign='center', font_size='16sp'))
        
        btn_pdf = ModernButton(text="📄 Sonuçları PDF Olarak İndir", bg_color=COLOR_SECONDARY, size_hint_y=0.2)
        btn_pdf.bind(on_press=lambda x: self.create_pdf(now_str))
        card.add_widget(btn_pdf)
        
        btn_back = ModernButton(text="Menüye Dön", bg_color=COLOR_SUCCESS, size_hint_y=0.2)
        btn_back.bind(on_press=lambda x: setattr(self.manager, 'current', 'guest_menu'))
        card.add_widget(btn_back)
        
        root.add_widget(card)
        self.add_widget(root)

    def create_pdf(self, now_str):
        app = App.get_running_app()
        clean_name = app.guest_name.replace(" ", "_")
        pdf_path = os.path.join(BASE_DIR, f"Anket_{clean_name}.pdf")
        
        c = canvas.Canvas(pdf_path, pagesize=letter)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, 755, "Van Edremit Kizilay Engelsiz Yasam Daire Baskanligi")
        c.setFont("Helvetica", 11)
        c.drawString(50, 735, "Engelsiz Yasam Anketi Sonuclari")
        c.drawString(50, 715, f"Katilimci: {app.guest_name}")
        if app.user_email:
            c.drawString(50, 700, f"Unvan: {app.user_title}")
            c.drawString(50, 685, f"E-posta: {app.user_email}")
            c.drawString(50, 670, f"Tarih: {now_str}")
            c.line(50, 660, 550, 660)
            y = 630
        else:
            c.drawString(50, 700, f"Tarih: {now_str}")
            c.line(50, 690, 550, 690)
            y = 660
            
        for idx, item in enumerate(self.data[:5]):
            c.setFont("Helvetica-Bold", 10)
            c.drawString(50, y, f"Soru {idx+1}: {item['soru'][:60]}")
            y -= 15
            c.setFont("Helvetica", 10)
            c.drawString(65, y, f"Cevap: {self.answers[idx]}")
            y -= 25
            
        c.save()
        show_popup("Başarılı", f"Sonuçlar PDF olarak kaydedildi:\n{pdf_path}")


# 14. HAKKIMIZDA
class AboutScreen(BackgroundScreen):
    def on_enter(self):
        self.clear_widgets()
        root = BoxLayout(orientation='vertical', padding=15, spacing=10)
        card = ModernCard(orientation='vertical', padding=15, spacing=10)
        
        card.add_widget(Label(text="[b]Hakkımızda[/b]", markup=True, font_size='20sp', size_hint_y=0.12))
        
        about_text = (
            "Bu mobil uygulama, [b]Van Edremit Kızılay Engelsiz Yaşam Daire Başkanlığı[/b] "
            "adına toplumda engelsiz yaşam bilincini ve erişilebilirliği artırmak amacıyla "
            "[b]Anka Sosyal Gelişim Platformu[/b] tarafından geliştirilmiştir.\n\n"
            "Uygulamanın temel gayesi; engelli bireylerle iletişimde doğru, saygılı ve kapsayıcı "
            "bir hitap dilini yaygınlaştırmak ve farkındalık düzeyini artırmaktır."
        )
        card.add_widget(Label(text=about_text, markup=True, text_size=(300, None), font_size='13sp', halign='center', size_hint_y=0.6))
        
        btn_tts = ModernButton(text="🔊 Metni Sesli Oku", bg_color=COLOR_WARNING, size_hint_y=0.14)
        btn_tts.bind(on_press=lambda x: speak_text("Bu mobil uygulama, Van Edremit Kızılay Engelsiz Yaşam Daire Başkanlığı adına toplumda engelsiz yaşam bilincini artırmak amacıyla Anka Sosyal Gelişim Platformu tarafından geliştirilmiştir."))
        card.add_widget(btn_tts)
        
        btn_back = ModernButton(text="Menüye Dön", bg_color=COLOR_MUTED, size_hint_y=0.14)
        btn_back.bind(on_press=lambda x: setattr(self.manager, 'current', 'guest_menu'))
        card.add_widget(btn_back)
        
        root.add_widget(card)
        self.add_widget(root)
        speak_text("Hakkımızda sayfası açıldı.")


# 15. İLETİŞİM & GERİ BİLDİRİM FORMU
class FeedbackScreen(BackgroundScreen):
    def on_enter(self):
        self.clear_widgets()
        app = App.get_running_app()
        root = BoxLayout(orientation='vertical', padding=15, spacing=8)
        card = ModernCard(orientation='vertical', padding=14, spacing=7)
        
        card.add_widget(Label(text="[b]İletişim & Geri Bildirim Formu[/b]", markup=True, font_size='16sp', size_hint_y=0.08))
        
        box_n = BoxLayout(spacing=6, size_hint_y=0.12)
        self.name_in = ModernTextInput(text=app.guest_name, hint_text="Adınız Soyadınız", multiline=False, size_hint_x=0.76)
        btn_mic_n = ModernButton(text="🎙️ Söyle", bg_color=COLOR_SECONDARY, size_hint_x=0.24)
        btn_mic_n.bind(on_press=lambda x: open_voice_input(self.name_in, "Ad Soyad"))
        box_n.add_widget(self.name_in)
        box_n.add_widget(btn_mic_n)
        card.add_widget(box_n)
        
        self.email_in = ModernTextInput(text=app.user_email, hint_text="E-posta Adresiniz", multiline=False, size_hint_y=0.12)
        card.add_widget(self.email_in)
        
        box_m = BoxLayout(spacing=6, size_hint_y=0.34)
        self.msg_in = ModernTextInput(hint_text="Görüş, öneri veya mesajınız...", multiline=True, size_hint_x=0.76)
        btn_mic_m = ModernButton(text="🎙️ Mesajı\nSöyle", bg_color=COLOR_SECONDARY, size_hint_x=0.24)
        btn_mic_m.bind(on_press=lambda x: open_voice_input(self.msg_in, "Mesaj"))
        box_m.add_widget(self.msg_in)
        box_m.add_widget(btn_mic_m)
        card.add_widget(box_m)
        
        btn_send = ModernButton(text="Gönder", bg_color=COLOR_SUCCESS, size_hint_y=0.16)
        btn_send.bind(on_press=self.send_feedback)
        card.add_widget(btn_send)
        
        btn_back = ModernButton(text="Menüye Dön", bg_color=COLOR_MUTED, size_hint_y=0.14)
        btn_back.bind(on_press=lambda x: setattr(self.manager, 'current', 'guest_menu'))
        card.add_widget(btn_back)
        
        root.add_widget(card)
        self.add_widget(root)
        speak_text("Geri bildirim formu açıldı.")

    def send_feedback(self, instance):
        n = self.name_in.text.strip()
        e = self.email_in.text.strip()
        m = self.msg_in.text.strip()
        if not (n and e and m):
            show_popup("Uyarı", "Lütfen tüm alanları doldurunuz.")
            return
        save_feedback(n, e, m)
        show_popup("Teşekkürler", "Geri bildiriminiz Van Edremit Kızılay Engelsiz Yaşam Daire Başkanlığı'na iletilmek üzere kaydedildi.")
        self.msg_in.text = ""
        self.manager.current = "guest_menu"


# 16. EMEĞİ GEÇENLER & GELİŞTİRİCİ
class CreditsScreen(BackgroundScreen):
    def on_enter(self):
        self.clear_widgets()
        root = BoxLayout(orientation='vertical', padding=15, spacing=10)
        card = ModernCard(orientation='vertical', padding=15, spacing=10)
        
        card.add_widget(Label(text="[b]Emeği Geçenler & Geliştirici[/b]", markup=True, font_size='18sp', size_hint_y=0.14))
        
        credits_text = (
            "[b]Geliştirici & Yazılım Mimarı:[/b]\n"
            "Ferdi CANCAN\n\n"
            "[b]Geliştirici Platform:[/b]\n"
            "Anka Sosyal Gelişim Platformu\n\n"
            "[b]Kurum & Proje Sahibi:[/b]\n"
            "Van Edremit Kızılay Engelsiz Yaşam Daire Başkanlığı\n\n"
            "[b]Yönetim Ekibi:[/b]\n"
            "Anka Kuşu Sosyal Gelişim Platformu"
        )
        card.add_widget(Label(text=credits_text, markup=True, text_size=(300, None), font_size='13sp', halign='center', size_hint_y=0.6))
        
        btn_tts = ModernButton(text="🔊 Sesli Oku", bg_color=COLOR_WARNING, size_hint_y=0.13)
        btn_tts.bind(on_press=lambda x: speak_text("Geliştirici: Ferdi Cancan. Geliştirici Platform: Anka Sosyal Gelişim Platformu. Kurum: Van Edremit Kızılay Engelsiz Yaşam Daire Başkanlığı. Yönetim Ekibi: Anka Kuşu Sosyal Gelişim Platformu."))
        card.add_widget(btn_tts)
        
        btn_back = ModernButton(text="Menüye Dön", bg_color=COLOR_MUTED, size_hint_y=0.13)
        btn_back.bind(on_press=lambda x: setattr(self.manager, 'current', 'guest_menu'))
        card.add_widget(btn_back)
        
        root.add_widget(card)
        self.add_widget(root)
        speak_text("Emeği geçenler ve geliştirici bilgileri sayfası.")


# 17. SORU EKLEME
class AddQuestionScreen(BackgroundScreen):
    def on_enter(self):
        self.clear_widgets()
        root = BoxLayout(orientation='vertical', padding=15, spacing=8)
        card = ModernCard(orientation='vertical', padding=14, spacing=7)
        
        card.add_widget(Label(text="[b]Yeni Soru Ekle[/b]", markup=True, font_size='16sp', size_hint_y=0.09))
        
        box_q = BoxLayout(spacing=6, size_hint_y=0.25)
        self.q_text = ModernTextInput(hint_text="Soru metni...", multiline=True, size_hint_x=0.76)
        btn_mic_q = ModernButton(text="🎙️ Söyle", bg_color=COLOR_SECONDARY, size_hint_x=0.24)
        btn_mic_q.bind(on_press=lambda x: open_voice_input(self.q_text, "Soru Metni"))
        box_q.add_widget(self.q_text)
        box_q.add_widget(btn_mic_q)
        card.add_widget(box_q)
        
        self.opt1 = ModernTextInput(hint_text="1. Seçenek", multiline=False, size_hint_y=0.12)
        self.opt2 = ModernTextInput(hint_text="2. Seçenek", multiline=False, size_hint_y=0.12)
        self.opt3 = ModernTextInput(hint_text="3. Seçenek", multiline=False, size_hint_y=0.12)
        
        card.add_widget(self.opt1)
        card.add_widget(self.opt2)
        card.add_widget(self.opt3)
        
        btn_save = ModernButton(text="Kaydet", bg_color=COLOR_SUCCESS, size_hint_y=0.15)
        btn_save.bind(on_press=self.save_question)
        card.add_widget(btn_save)
        
        btn_back = ModernButton(text="Geri Dön", bg_color=COLOR_MUTED, size_hint_y=0.13)
        btn_back.bind(on_press=lambda x: setattr(self.manager, 'current', 'admin_panel'))
        card.add_widget(btn_back)
        
        root.add_widget(card)
        self.add_widget(root)

    def save_question(self, instance):
        if not (self.q_text.text and self.opt1.text and self.opt2.text and self.opt3.text):
            show_popup("Hata", "Tüm alanları doldurunuz.")
            return
        data = load_data()
        data["questions"].append({
            "soru": self.q_text.text.strip(),
            "secenekler": [self.opt1.text.strip(), self.opt2.text.strip(), self.opt3.text.strip()]
        })
        save_data(data)
        show_popup("Başarılı", "Soru eklendi.")
        self.manager.current = "admin_panel"


# 18. SORU SİL / ÇIKAR
class DeleteQuestionScreen(BackgroundScreen):
    def on_enter(self):
        self.clear_widgets()
        root = BoxLayout(orientation='vertical', padding=12, spacing=8)
        card = ModernCard(orientation='vertical', padding=12, spacing=8)
        
        card.add_widget(Label(text="[b]Soru Silme & Çıkarma[/b]", markup=True, font_size='16sp', size_hint_y=0.1))
        
        scroll = ScrollView(size_hint=(1, 0.76))
        grid = GridLayout(cols=1, spacing=8, size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))
        
        data = load_data()
        for idx, q in enumerate(data["questions"]):
            box = ModernCard(size_hint_y=None, height=42, padding=4, bg_color=(0.14, 0.20, 0.29, 1))
            box.add_widget(Label(text=q["soru"][:24] + "...", font_size='12sp'))
            btn = ModernButton(text="Sil", size_hint_x=0.3, bg_color=COLOR_PRIMARY)
            btn.bind(on_press=lambda inst, i=idx: self.delete_q(i))
            box.add_widget(btn)
            grid.add_widget(box)
            
        scroll.add_widget(grid)
        card.add_widget(scroll)
        
        btn_back = ModernButton(text="Geri Dön", bg_color=COLOR_MUTED, size_hint_y=0.14)
        btn_back.bind(on_press=lambda x: setattr(self.manager, 'current', 'admin_panel'))
        card.add_widget(btn_back)
        
        root.add_widget(card)
        self.add_widget(root)

    def delete_q(self, index):
        data = load_data()
        if len(data["questions"]) <= 1:
            show_popup("Hata", "En az 1 soru sistemde kalmalıdır.")
            return
        data["questions"].pop(index)
        save_data(data)
        self.on_enter()


# 19. ŞİFRE DEĞİŞTİR (YÖNETİCİ)
class ChangePassScreen(BackgroundScreen):
    def on_enter(self):
        self.clear_widgets()
        root = BoxLayout(orientation='vertical', padding=20, spacing=10)
        card = ModernCard(orientation='vertical', padding=15, spacing=10)
        
        card.add_widget(Label(text="[b]Şifre Güncelleme[/b]", markup=True, font_size='17sp', size_hint_y=0.2))
        self.new_pass = ModernTextInput(hint_text="Yeni Şifre", password=True, multiline=False, size_hint_y=0.2)
        card.add_widget(self.new_pass)
        
        btn_save = ModernButton(text="Şifreyi Güncelle", bg_color=COLOR_SUCCESS, size_hint_y=0.2)
        btn_save.bind(on_press=self.update_password)
        card.add_widget(btn_save)
        
        btn_back = ModernButton(text="İptal", bg_color=COLOR_MUTED, size_hint_y=0.16)
        btn_back.bind(on_press=lambda x: setattr(self.manager, 'current', 'admin_panel'))
        card.add_widget(btn_back)
        
        root.add_widget(card)
        self.add_widget(root)

    def update_password(self, instance):
        np = self.new_pass.text.strip()
        if not np:
            show_popup("Hata", "Yeni şifre boş olamaz.")
            return
        app = App.get_running_app()
        data = load_data()
        if app.current_admin_user in data.get("admins", {}):
            data["admins"][app.current_admin_user] = np
            save_data(data)
            show_popup("Başarılı", "Şifreniz güncellendi.")
            self.manager.current = "admin_panel"
        else:
            show_popup("Hata", "Şifre güncellenemedi.")


class SurveyApp(App):
    guest_name = ""
    user_email = ""
    user_title = "Üye / Gönüllü"
    user_duty = "Henüz atanmış bir görev bulunmuyor."
    selected_user_email = ""
    is_super_admin = False
    current_admin_user = ""

    def build(self):
        sm = ScreenManager(transition=FadeTransition())
        sm.add_widget(EntryChoiceScreen(name="entry_choice"))
        sm.add_widget(MemberLoginScreen(name="member_login_screen"))
        sm.add_widget(RegisterScreen(name="register_screen"))
        sm.add_widget(GuestNameScreen(name="guest_name_screen"))
        sm.add_widget(GuestMenuScreen(name="guest_menu"))
        sm.add_widget(AdminLoginScreen(name="admin_login_screen"))
        sm.add_widget(AdminPanel(name="admin_panel"))
        sm.add_widget(MemberManagementScreen(name="member_management_screen"))
        sm.add_widget(AssignDutyScreen(name="assign_duty_screen"))
        sm.add_widget(AdminAddUserScreen(name="admin_add_user_screen"))
        sm.add_widget(StatsScreen(name="stats_screen"))
        sm.add_widget(AddAdminScreen(name="add_admin_screen"))
        sm.add_widget(SurveyScreen(name="survey_screen"))
        sm.add_widget(AboutScreen(name="about_screen"))
        sm.add_widget(FeedbackScreen(name="feedback_screen"))
        sm.add_widget(CreditsScreen(name="credits_screen"))
        sm.add_widget(AddQuestionScreen(name="add_question_screen"))
        sm.add_widget(DeleteQuestionScreen(name="delete_question_screen"))
        sm.add_widget(ChangePassScreen(name="change_pass_screen"))
        return sm


if __name__ == "__main__":
    SurveyApp().run()
