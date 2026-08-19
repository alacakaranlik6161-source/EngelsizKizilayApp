[app]
title = Engelsiz Yasam Kizilay
package.name = engelsizyasamkizilay
package.domain = org.ankagelisim.kizilay
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,ttf,mp3
version = 1.0.0

# Gerekli Kütüphaneler
requirements = python3,kivy==2.3.0,reportlab,gtts,urllib3,charset_normalizer,idna,requests

# İkon
icon.filename = %(source.dir)s/kizilay.png

# Android İzinleri
android.permissions = INTERNET,RECORD_AUDIO,READ_EXTERNAL_STORAGE,WRITE_EXTERNAL_STORAGE
# Hedef Mimari
android.api = 33
android.minapi = 21
android.sdk = 33
android.ndk = 25b
android.archs = arm64-v8a
android.allow_backup = True
android.accept_sdk_license = True

[buildozer]
log_level = 2
warn_on_root = 1
