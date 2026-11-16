# Panduan Bulk Quiz dan Placement Test

Panduan singkat untuk pengelola kursus. Nama menu dapat sedikit berbeda sesuai bahasa Odoo.

## A. Impor banyak soal (Bulk Quiz)

### 1. Buka quiz di backend

1. Masuk ke backend Odoo, buka **eLearning → Courses**.
2. Pilih kursus yang akan diberi quiz.
3. Di tab **Content**, buka materi berjenis **Quiz**. Jika belum ada, buat materi baru dan pilih jenis Quiz.
4. Pada formulir quiz, gunakan tombol **Download Excel Template** untuk mengunduh format resmi.

### 2. Isi file Excel

- Isi satu soal pada setiap baris di worksheet pertama.
- Jangan mengganti atau menghapus judul kolom. Simpan sebagai **`.xlsx`**.
- Hapus baris contoh sebelum impor agar contoh tidak ikut menjadi soal.
- Kolom **Question** wajib diisi. **Weight** harus lebih dari 0 (kosong berarti 1). **Required** dan **Allow Partial Score** diisi `TRUE` atau `FALSE`.
- Tipe yang dapat diimpor: `single_choice`, `multiple_choice`, `true_false`, `short_answer`, `essay`, dan `listening`.

Ketentuan sesuai jenis:

| Jenis | Yang perlu diisi |
|---|---|
| `single_choice` | Minimal 2 opsi; tepat 1 kolom `Correct` bernilai `TRUE`, dan setidaknya 1 opsi salah (`FALSE`). |
| `multiple_choice` | Minimal 2 opsi; satu atau lebih jawaban benar (`TRUE`) dan setidaknya 1 jawaban salah (`FALSE`). |
| `true_false` | Opsi `True` dan `False`, dengan tepat satu jawaban benar. Bisa memakai kolom opsi seperti contoh template. |
| `short_answer` | Isi **Accepted Answers**. Pisahkan variasi jawaban dengan tanda `|`, contoh: `xie xie|谢谢`. |
| `essay` | Isi **Grading Rubric** agar pengajar tahu kriteria penilaian. Jawaban perlu diperiksa pengajar. |
| `listening` | Isi **Listening Answer Type** dengan `choice` atau `short_answer`, lalu isi kolom jawaban yang sesuai. Audio dilampirkan ke soal setelah impor. |

Kolom **Answer 1–4**, **Correct 1–4**, dan **Comment 1–4** digunakan untuk pilihan jawaban; opsi yang tidak dipakai boleh dibiarkan kosong. Untuk soal listening, file audio tidak dimasukkan ke Excel.

### 3. Impor dan periksa soal

1. Kembali ke formulir quiz, klik **Import Excel**.
2. Pilih file `.xlsx`, lalu jalankan impor.
3. Periksa soal dan kunci jawabannya di daftar Questions. Impor **menambahkan soal di bagian akhir** dan tidak menghapus soal lama.
4. Lampirkan audio pada soal listening, uji quiz, lalu publikasikan jika sudah benar.

Jika impor gagal, periksa kembali format `.xlsx`, nama kolom, nilai `TRUE/FALSE`, serta persyaratan tipe soal pada tabel di atas. Tombol impor hanya tersedia bagi pengguna yang memiliki hak mengelola konten kursus.

## B. Menyiapkan dan mengirim Placement Test

### 1. Siapkan survei placement test

1. Buka **eLearning → Reporting → Student & Internal Surveys**.
2. Buka survei yang akan digunakan atau buat survei baru.
3. Aktifkan **Placement Test**, lalu simpan.
4. Pada tab **Placement Test**, tambahkan setiap kursus yang hendak diuji. Isi **Passing Score (%)** untuk masing-masing kursus, misalnya 70.
5. Buat atau buka pertanyaan survei. Pada setiap pertanyaan, isi **Placement Course** sesuai kursus yang diuji. Ini penting agar hasil dihitung per kursus.
6. Bila menggunakan tipe soal esai atau jawaban bebas yang perlu dinilai pengajar, rencanakan pemeriksaan manual setelah peserta menyelesaikan test.

Untuk hasil otomatis yang dapat dibandingkan per kursus, pastikan setiap kursus memiliki pertanyaan yang ditandai ke kursus tersebut dan memiliki nilai/skor yang dapat dinilai otomatis. Jika peserta tidak mendapat pertanyaan untuk suatu kursus, hasilnya akan **No Questions Selected**, bukan otomatis lulus.

### 2. Kirim kepada student

1. Dari survei, pilih **Invite/Share** untuk membuka undangan.
2. Pilih kontak student yang akan mengikuti test, atau pilih **Contact Segment** student dan klik **Load Contacts**.
3. Pastikan daftar penerima dan alamat emailnya benar sebelum mengirim. Jangan memilih kontak internal saja jika targetnya student.
4. Kirim undangan. Student menerima tautan untuk mengerjakan survei; tautan dapat dibuka tanpa masuk sebagai pengguna internal Odoo.

### 3. Tinjau hasil dan rekomendasi

Setelah student mengirim jawaban, buka respons/partisipasi survei tersebut. Status harus **Done** agar tab **Placement Results** terisi.

| Hasil | Arti / tindakan |
|---|---|
| **Skip Recommended** | Skor kursus mencapai passing score; kursus tersebut direkomendasikan untuk dilewati. |
| **Course Review Recommended** | Skor belum mencapai passing score; student direkomendasikan mengulang atau meninjau kursus tersebut. |
| **Instructor Review Required** | Ada jawaban yang memerlukan penilaian pengajar. Tinjau jawaban, lalu pilih **Instructor Decision**: Skip Course atau Review Course. |
| **No Questions Selected** | Tidak ada pertanyaan kursus itu yang masuk ke pengerjaan student. Jangan anggap sebagai lulus; periksa konfigurasi dan pertanyaan yang diberikan. |

Rekomendasi ini membantu menentukan materi belajar berikutnya; keputusan akhir tetap dapat diperiksa pengajar.

## Checklist sebelum digunakan

- [ ] Soal sudah ditandai ke kursus yang benar.
- [ ] Passing score tiap kursus sudah diisi.
- [ ] Email student benar dan student dipilih sebagai penerima.
- [ ] Soal pilihan ganda punya kunci jawaban yang benar.
- [ ] Soal esai/jawaban bebas dan audio sudah ditinjau sesuai kebutuhan.
- [ ] Satu respons percobaan sudah diuji sebelum mengirim ke banyak student.
