╔══════════════════════════════════════════════════════════════╗
║ gwperintahin v1.0 ║
║ Windows Macro Agent Toolkit ║
╚══════════════════════════════════════════════════════════════╝

─── PENGANTAR ──────────────────────────────────────────────────

gwperintahin adalah tools Windows yang memungkinkan Anda membuat,
menyimpan, dan menjalankan macro otomatisasi layar (klik, ketik,
tunggu, deteksi warna/gambar) tanpa perlu install Python.

─── CARA PENGGUNAAN ─────────────────────────────────────────────

  1. Buka gwperintahin.exe
  2. Buat macro via GUI (tambah step, atur parameter)
  3. Klik "Save" untuk menyimpan macro
  4. Klik "Export BAT" → otomatis generate.bat launcher
  5. Double-click.bat kapanpun untuk menjalankan macro

─── STRUKTUR FOLDER ─────────────────────────────────────────────

  gwperintahin/
  ├── gwperintahin.exe ← GUI Builder (buka ini)
  ├── executor.exe ← Runtime engine (jangan dihapus)
  ├── macros/ ← Macro definitions (.json)
  ├── templates/ ← Screenshot templates (.png)
  ├── logs/ ← Runtime logs
  ├── exports/ ←.bat launcher yang di-generate
  └── README.txt ← File ini

─── TIPE ACTION YANG DIDUKUNG ───────────────────────────────────

  Action Deskripsi
  ──────────────────────────────────────────────────────────────
  Wait for Image Tunggu sampai gambar muncul di layar
  Wait for Color Tunggu sampai warna tertentu muncul
  Click Image Klik di tengah gambar yang ditemukan
  Click Color Klik pixel dengan warna tertentu
  Click Coordinate Klik koordinat absolut (x, y)
  Right Click Coord Klik kanan di koordinat
  Double Click Double klik di koordinat/gambar
  Type Text Ketik teks (dengan delay per karakter)
  Press Key Tekan tombol / shortcut keyboard
  Scroll Scroll mouse (atas/bawah)
  Wait (Seconds) Delay / tunggu beberapa detik
  Wait for Window Tunggu window dengan judul tertentu
  Focus Window Fokuskan window tertentu
  Screenshot Capture layar (untuk log/debug)
  Loop Ulangi group steps N kali
  If/Else Condition Kondisional sederhana
  Set Variable Set variable untuk kondisi
  Exit Macro Stop macro

─── DETECTION TOOLS ──────────────────────────────────────────────

  Color Picker Klik pixel di layar → ambil hex color
  Capture Region Drag area → save sebagai template.png
  Coord Inspector Lihat koordinat mouse real-time

─── DISTRIBUSI ──────────────────────────────────────────────────

  Cukup extract folder gwperintahin dan jalankan gwperintahin.exe.
  Tidak perlu install Python atau dependencies apapun.

─── SYSTEM REQUIREMENTS ─────────────────────────────────────────

  • Windows 10 / 11 (64-bit)
  • Monitor single screen
  • Mouse dan keyboard

─── SUPPORT ─────────────────────────────────────────────────────

  Untuk bantuan lebih lanjut, hubungi pengembang.

─── LICENSE ─────────────────────────────────────────────────────

  MIT License — bebas digunakan dan dimodifikasi.

╔══════════════════════════════════════════════════════════════╗
║ Selamat menggunakan gwperintahin! ║
║ "Perintahin komputermu, biar dia yang kerja." ║
╚══════════════════════════════════════════════════════════════╝
