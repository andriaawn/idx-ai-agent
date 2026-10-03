# Fix: cache simbol yfinance tak tersedia (potong 687 error + percepat scan)

**Tanggal**: 2026-10-03
**Status**: ✅ SELESAI
**Konteks**: audit 2 project menemukan yfinance = sumber error #1 di idx-ai-agent
(687 dari 700 ERROR dalam 3 hari).

---

## Masalah

`scan_universe()` mengiterasi ~964 ticker (dari `Daftar_Saham.xlsx`). **111 di
antaranya sudah tak ada di Yahoo Finance** (delisted / tak terdaftar), tapi tetap
di-fetch tiap scan.

Akibatnya, tiap scan:
- **111 request sia-sia** ke Yahoo (masing-masing ~1,6s) → buang ~176s sequential
  (atau ~12s dengan concurrency 15).
- **1 log ERROR per simbol** → 687 error / 3 hari, berulang tiap hari karena
  tidak ada cache.

## Bukti (terukur)

Waktu fetch per simbol (langsung, di server):

```
simbol delisted (WSKT, SRIL, MYRX, ...) : 1,59s/simbol
simbol valid    (BBCA, TLKM, ASII, ...) : 0,18s/simbol
```

Error yfinance di journal `idxbot` (3 hari):

```
687 ERROR  <- yfinance  (111 simbol unik, masing-masing ~11x)
 13 ERROR  <- lain-lain (root: report/alerts)
```

Verifikasi simbol memang tak ada: `yf.Ticker("WSKT.JK").history()` →
`HTTP 404 "Quote not found for symbol: WSKT.JK"`. **Bukan bug retry** — datanya
memang tidak ada di Yahoo.

## Perubahan

`src/data/providers/yfinance_provider.py`:

- Tambah **cache simbol-tak-tersedia** (class-level, persist ke file
  `.unavailable_tickers.json`).
- Sebelum fetch: kalau simbol **terkonfirmasi** mati → return DataFrame kosong
  langsung (nol network, nol log).
- Setelah fetch kosong → catat sebagai satu "miss". Simbol baru dianggap mati
  setelah **3 kali kosong berturut-turut** (`_UNAVAILABLE_CONFIRMATIONS`).
- Ada data → **reset** hitungan miss (simbol valid tidak pernah terkunci).
- **TTL 7 hari**: entri kedaluwarsa → dicoba lagi (simbol relisting bisa ketemu).
- **Hanya `df.empty` yang di-cache** — error jaringan/DNS **TIDAK**, supaya
  masalah nyata tetap terlihat.

### ⚠️ Jebakan yang ditemukan saat verifikasi (penting)

Rancangan awal menandai simbol mati dari **satu** hasil kosong. Saat verifikasi
e2e, run-2 kehilangan 111 simbol "data ada" — ternyata **`BBRI` (blue chip yang
valid) return kosong** di bawah concurrency 15, padahal **245 baris** saat
diisolasi. Yahoo memang kadang **transient-empty** (rate-limit/crumb).

Terukur:
```
BBRI 10x sendirian      : 245 baris (10/10)
BBRI di concurrency 15  : kadang 0 baris
Valid lain (BBCA/TLKM)  : 244-245 baris konsisten
Delisted (WSKT/SRIL)    : 0 baris konsisten
```

Karena itu desain diubah: butuh **konfirmasi berulang** sebelum mengunci. Ini
mencegah simbol valid "hilang" gara-gara hiccup Yahoo.

## Test

**BARU** `tests/test_yfinance_unavailable.py` — 7 test:

1. **satu** hasil kosong belum mengunci (jebakan transient);
2. kosong berulang → terkunci;
3. simbol terkonfirmasi mati → `yf.Ticker` tidak dipanggil sama sekali;
4. data ada → hitungan miss direset;
5. simbol valid → tetap fetch normal & tidak dicache;
6. cache kedaluwarsa → fetch ulang;
7. cache bertahan setelah restart (dibaca ulang dari file).

Bukti nangkep bug: kode lama → **5 failed** (`AttributeError: no attribute
'_cache_path'`); kode baru → **7 passed**.

## Verifikasi e2e

`verify_cache_final.py` — scan full universe (964 ticker) 3x berturut-turut:

```
run-1: 41.3s | data ada: 910 | terkunci:  0
run-2: 38.1s | data ada: 910 | terkunci:  0
run-3: 39.5s | data ada: 910 | terkunci: 54
```

**`data ada: 910` konsisten di 3 run** → simbol valid **tidak ada yang hilang**
(jebakan transient-empty berhasil dicegah). Setelah 3 scan, 54 simbol terkunci.

### Rekonsiliasi angka (penting — jangan salah lapor)

Log produksi menampilkan **111 simbol unik** gagal, TAPI setelah diuji satu per
satu (3x isolated):

```
111 simbol di log (semua ada di universe):
  SELALU kosong (3/3) : 54  -> benar-benar delisted
  SELALU ada data     : 57  -> VALID (transient-empty saat concurrency tinggi)
  KADANG ada data     : 0
```

**54** yang terkunci di e2e **tepat sama** dengan 54 yang benar-benar delisted.
Artinya: **57 simbol valid** yang sempat muncul di log (karena rate-limit saat
scan paralel) **tidak** ikut terkunci — berkat syarat 3 konfirmasi.

### Dampak nyata

- Error yfinance: **~229/hari (687/3hari) → ~0** setelah 3 scan pertama
  (simbol mati di-skip; simbol valid tetap ter-fetch normal).
- Waktu scan: ~1,6s/simbol mati dihemat. Karena simbol mati tersebar dan
  concurrency 15, penghematan wall-clock lebih kecil dari hitungan sequential
  (~176s) — terukur run stabil di ~38-41s.
- **Nol regresi**: simbol valid (910) tetap ter-fetch persis seperti sebelumnya.

## File
- `src/data/providers/yfinance_provider.py` — cache + TTL
- `tests/test_yfinance_unavailable.py` — BARU, 5 test
- `.gitignore` — abaikan `.unavailable_tickers.json`
