# Panduan Lengkap Menjalankan Project Odoo Ini

## 1. Project ini apa

Folder ini:

`C:\Users\SOULMATE PLUS IP\Documents\odoo`

adalah source tree penuh **Odoo 19**.

Ini bukan addon kecil. Isi utamanya:

- `odoo-bin`: entry point untuk menjalankan server atau command Odoo
- `odoo/`: core framework Odoo
- `odoo/addons/`: addon bawaan Odoo
- `addons/`: addon tambahan yang ikut ada di source tree ini
- `requirements.txt`: dependency Python
- `odoo.conf`: file konfigurasi local untuk environment dev ini

## 2. Kondisi environment di mesin ini

Setup yang sudah dipakai di mesin Anda:

- Project root: `C:\Users\SOULMATE PLUS IP\Documents\odoo`
- Python: `C:\Users\SOULMATE PLUS IP\AppData\Local\Programs\Python\Python312\python.exe`
- PostgreSQL host: `localhost`
- PostgreSQL port: `5432`
- PostgreSQL user: `odoo`
- PostgreSQL password: `odoo123`
- Database dev Odoo: `odoo_dev`
- HTTP port Odoo dev: `8070`
- Gevent port Odoo dev: `8073`
- Log file dev: `C:\Users\SOULMATE PLUS IP\Documents\odoo\odoo-dev.log`
- Data dir dev: `C:\Users\SOULMATE PLUS IP\Documents\odoo\.odoo-data`

## 3. Kenapa config-nya tidak pakai default

Ada beberapa alasan:

1. Port default Odoo `8069` sudah dipakai service Odoo Windows yang sudah terinstall di mesin ini.
2. Karena itu instance repo ini dipisah ke port `8070`.
3. PostgreSQL Windows di mesin ini gagal membuat database Odoo jika memakai default `template0`.
4. Karena itu config repo ini memakai `db_template = template1`.
5. `data_dir` dipindah ke dalam workspace karena lokasi default AppData sempat kena masalah izin tulis pada environment ini.

## 4. File konfigurasi yang dipakai

File utama yang dipakai untuk menjalankan repo ini adalah:

[odoo.conf](</C:/Users/SOULMATE PLUS IP/Documents/odoo/odoo.conf:1>)

Isi pentingnya:

- `db_host = localhost`
- `db_port = 5432`
- `db_user = odoo`
- `db_password = odoo123`
- `db_template = template1`
- `http_port = 8070`
- `gevent_port = 8073`
- `data_dir = C:\Users\SOULMATE PLUS IP\Documents\odoo\.odoo-data`
- `logfile = C:\Users\SOULMATE PLUS IP\Documents\odoo\odoo-dev.log`

## 5. Apa yang sudah disetup

Yang sudah dilakukan:

1. Python 3.12 dipasang.
2. Dependency Python dari `requirements.txt` dipasang.
3. User PostgreSQL `odoo` dipakai untuk koneksi Odoo.
4. Config local repo dibuat di `odoo.conf`.
5. Database dev `odoo_dev` berhasil diinisialisasi.

## 6. Cara membuka terminal yang benar

Anda harus menjalankan command Odoo dari **PowerShell** atau **Command Prompt**, bukan dari dalam prompt Python `>>>`.

Yang benar:

```powershell
cd "C:\Users\SOULMATE PLUS IP\Documents\odoo"
```

Kalau Anda melihat prompt seperti ini:

```text
PS C:\Users\SOULMATE PLUS IP\Documents\odoo>
```

berarti Anda sudah ada di terminal yang benar.

Kalau Anda melihat prompt seperti ini:

```python
>>>
```

itu berarti Anda sedang berada di Python interactive shell, dan command seperti `.\odoo-bin` tidak boleh dijalankan di sana.

Kalau terlanjur masuk ke Python shell, keluar dulu:

```python
exit()
```

## 7. Cara menjalankan project ini

### Jalankan di foreground

Ini cara paling aman untuk development karena Anda bisa langsung lihat log:

```powershell
cd "C:\Users\SOULMATE PLUS IP\Documents\odoo"
& 'C:\Users\SOULMATE PLUS IP\AppData\Local\Programs\Python\Python312\python.exe' .\odoo-bin -c .\odoo.conf -d odoo_dev
```

Setelah itu buka browser:

```text
http://localhost:8070
```

### Jalankan di background

Kalau ingin jalan di background:

```powershell
Start-Process -FilePath 'C:\Users\SOULMATE PLUS IP\AppData\Local\Programs\Python\Python312\python.exe' `
  -ArgumentList '.\odoo-bin','-c','.\odoo.conf','-d','odoo_dev' `
  -WorkingDirectory 'C:\Users\SOULMATE PLUS IP\Documents\odoo' `
  -WindowStyle Hidden
```

Lalu buka:

```text
http://localhost:8070
```

## 8. Cara menghentikan server

Kalau jalan di foreground:

- tekan `Ctrl+C`

Kalau jalan di background:

```powershell
Get-Process python | Select-Object Id, ProcessName, Path
Stop-Process -Id <PID>
```

## 9. Command penting yang perlu Anda tahu

### Lihat bantuan umum

```powershell
& 'C:\Users\SOULMATE PLUS IP\AppData\Local\Programs\Python\Python312\python.exe' .\odoo-bin help
```

### Lihat bantuan command server

```powershell
& 'C:\Users\SOULMATE PLUS IP\AppData\Local\Programs\Python\Python312\python.exe' .\odoo-bin server --help
```

### Lihat bantuan command database

```powershell
& 'C:\Users\SOULMATE PLUS IP\AppData\Local\Programs\Python\Python312\python.exe' .\odoo-bin db --help
```

### Inisialisasi database

Database `odoo_dev` sudah dibuat, tapi kalau nanti perlu bikin lagi:

```powershell
& 'C:\Users\SOULMATE PLUS IP\AppData\Local\Programs\Python\Python312\python.exe' .\odoo-bin db -c .\odoo.conf init odoo_dev
```

### Install module

```powershell
& 'C:\Users\SOULMATE PLUS IP\AppData\Local\Programs\Python\Python312\python.exe' .\odoo-bin module install -c .\odoo.conf -d odoo_dev <nama_module>
```

Contoh:

```powershell
& 'C:\Users\SOULMATE PLUS IP\AppData\Local\Programs\Python\Python312\python.exe' .\odoo-bin module install -c .\odoo.conf -d odoo_dev sale_management
```

### Upgrade module

```powershell
& 'C:\Users\SOULMATE PLUS IP\AppData\Local\Programs\Python\Python312\python.exe' .\odoo-bin module upgrade -c .\odoo.conf -d odoo_dev <nama_module>
```

### Uninstall module

```powershell
& 'C:\Users\SOULMATE PLUS IP\AppData\Local\Programs\Python\Python312\python.exe' .\odoo-bin module uninstall -c .\odoo.conf -d odoo_dev <nama_module>
```

### Masuk ke Odoo shell

```powershell
& 'C:\Users\SOULMATE PLUS IP\AppData\Local\Programs\Python\Python312\python.exe' .\odoo-bin shell -c .\odoo.conf -d odoo_dev
```

### Hitung line of code

```powershell
& 'C:\Users\SOULMATE PLUS IP\AppData\Local\Programs\Python\Python312\python.exe' .\odoo-bin cloc
```

### Generate skeleton module baru

```powershell
& 'C:\Users\SOULMATE PLUS IP\AppData\Local\Programs\Python\Python312\python.exe' .\odoo-bin scaffold my_module .\addons
```

## 10. Cara cek log

Untuk lihat log terbaru:

```powershell
Get-Content .\odoo-dev.log -Tail 100
```

Kalau mau memantau terus:

```powershell
Get-Content .\odoo-dev.log -Wait
```

## 11. Cara reset database dev

Kalau database dev rusak atau ingin mulai ulang:

### Hapus database

```powershell
$env:PGPASSWORD='odoo123'
& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' -U odoo -h localhost -p 5432 -d postgres -c "DROP DATABASE IF EXISTS odoo_dev;"
```

### Buat ulang database

```powershell
& 'C:\Users\SOULMATE PLUS IP\AppData\Local\Programs\Python\Python312\python.exe' .\odoo-bin db -c .\odoo.conf init odoo_dev
```

## 12. Cara cek koneksi PostgreSQL

Untuk test koneksi user `odoo`:

```powershell
$env:PGPASSWORD='odoo123'
& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' -U odoo -h localhost -p 5432 -d postgres -c "SELECT current_user, current_database();"
```

## 13. Cara pasang dependency ulang

Kalau suatu saat dependency Python perlu dipasang ulang:

```powershell
cd "C:\Users\SOULMATE PLUS IP\Documents\odoo"
& 'C:\Users\SOULMATE PLUS IP\AppData\Local\Programs\Python\Python312\python.exe' -m pip install -r requirements.txt
```

## 14. Alur kerja harian yang disarankan

Untuk penggunaan normal, urutannya:

1. Buka PowerShell
2. Masuk ke folder project
3. Jalankan Odoo
4. Buka browser ke `http://localhost:8070`
5. Kerjakan perubahan code atau addon
6. Kalau ada perubahan module, upgrade module
7. Cek log kalau ada error

Command yang paling sering dipakai:

```powershell
cd "C:\Users\SOULMATE PLUS IP\Documents\odoo"
& 'C:\Users\SOULMATE PLUS IP\AppData\Local\Programs\Python\Python312\python.exe' .\odoo-bin -c .\odoo.conf -d odoo_dev
```

## 15. Hal penting yang harus diingat

1. Jangan jalankan command Odoo dari prompt `>>>`.
2. Jalankan command dari PowerShell atau `cmd`.
3. Repo ini memakai port `8070`, bukan `8069`.
4. Service Odoo Windows yang terinstall tetap terpisah dari repo dev ini.
5. File config repo ini adalah `odoo.conf`, bukan config Odoo yang ada di `C:\Program Files\Odoo ...`.

## 16. Troubleshooting

### A. Error karena Anda ada di prompt `>>>`

Gejala:

```python
>>> .\odoo-bin -c .\odoo.conf -d odoo_dev
```

Solusi:

- keluar dari Python dengan `exit()`
- jalankan command dari PowerShell

### B. Browser tidak bisa buka `localhost:8070`

Cek:

```powershell
Get-Content .\odoo-dev.log -Tail 100
```

Lalu jalankan ulang server:

```powershell
cd "C:\Users\SOULMATE PLUS IP\Documents\odoo"
& 'C:\Users\SOULMATE PLUS IP\AppData\Local\Programs\Python\Python312\python.exe' .\odoo-bin -c .\odoo.conf -d odoo_dev
```

### C. Database error saat startup

Cek koneksi PostgreSQL:

```powershell
$env:PGPASSWORD='odoo123'
& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' -U odoo -h localhost -p 5432 -d postgres -c "SELECT 1;"
```

### D. Database ingin dibersihkan total

Drop lalu init ulang `odoo_dev`.

## 17. File penting yang sebaiknya Anda baca

- [odoo.conf](</C:/Users/SOULMATE PLUS IP/Documents/odoo/odoo.conf:1>)
- [SETUP_DEV.md](</C:/Users/SOULMATE PLUS IP/Documents/odoo/SETUP_DEV.md:1>)
- [README.md](</C:/Users/SOULMATE PLUS IP/Documents/odoo/README.md:1>)
- [requirements.txt](</C:/Users/SOULMATE PLUS IP/Documents/odoo/requirements.txt:1>)

## 18. Ringkasan singkat

Kalau Anda lupa semuanya, cukup ingat ini:

```powershell
cd "C:\Users\SOULMATE PLUS IP\Documents\odoo"
& 'C:\Users\SOULMATE PLUS IP\AppData\Local\Programs\Python\Python312\python.exe' .\odoo-bin -c .\odoo.conf -d odoo_dev
```

Lalu buka:

```text
http://localhost:8070
```
