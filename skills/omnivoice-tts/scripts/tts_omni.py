# -*- coding: utf-8 -*-
"""用本地 omnivoice-tts (docker :7842) 按 SRT 合成解说轨。
- 逐句 POST /tts (voice=guoxue_default 或命令行指定)
- 每句按 SRT 槽位 atempo 压缩(上限 2.6, 两级)
- 按起始时间放置 amix 成 48kHz 立体声解说轨
用法: python tts_omni.py <srt> <out.wav> [voice] [speed]
"""
import re, sys, os, tempfile, json, time, urllib.request

HOST = 'http://localhost:7842'
WINGET = r'C:\Users\Administrator\AppData\Local\Microsoft\WinGet\Links'
FF = os.path.join(WINGET, 'ffmpeg.EXE')
FFPROBE = os.path.join(WINGET, 'ffprobe.EXE')

def parse_srt(p):
    txt = open(p, encoding='utf-8-sig').read().replace('\r\n', '\n')
    out = []
    for blk in re.split(r'\n\n+', txt.strip()):
        lines = [l for l in blk.split('\n') if l.strip()]
        if len(lines) < 2: continue
        m = None; text = ''
        for j, l in enumerate(lines):
            mm = re.match(r'(\d+):(\d+):(\d+),(\d+)\s*-->\s*(\d+):(\d+):(\d+),(\d+)', l)
            if mm:
                m = mm; text = ' '.join(lines[j+1:]); break
        if not m: continue
        g = [int(x) for x in m.groups()]
        t0 = g[0]*3600 + g[1]*60 + g[2] + g[3]/1000
        t1 = g[4]*3600 + g[5]*60 + g[6] + g[7]/1000
        out.append((t0, t1, text.strip()))
    return out

def dur_of(f):
    r = subprocess_run([FFPROBE, '-v', 'error', '-i', f, '-show_entries', 'format=duration',
                        '-of', 'csv=p=0'])
    return float(r.strip())

def subprocess_run(cmd):
    import subprocess
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f'cmd fail: {r.stderr[-300:]}')
    return r.stdout.strip()

def synth(text, out, voice, speed):
    payload = json.dumps({'text': text, 'voice': voice, 'speed': speed}).encode('utf-8')
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(HOST + '/tts', data=payload,
                                         headers={'Content-Type': 'application/json'})
            with urllib.request.urlopen(req, timeout=300) as resp:
                data = resp.read()
            if len(data) > 1000:
                open(out, 'wb').write(data)
                return
            raise RuntimeError(f'short body {len(data)}')
        except Exception as e:
            last = e; time.sleep(3)
    raise RuntimeError(f'tts fail after 3 tries: {last}')

def main():
    srt, outw = sys.argv[1], sys.argv[2]
    voice = sys.argv[3] if len(sys.argv) > 3 else 'guoxue_default'
    speed = float(sys.argv[4]) if len(sys.argv) > 4 else 1.0
    cues = parse_srt(srt)
    print(f'{len(cues)} cues  voice={voice} speed={speed}')
    tmp = tempfile.mkdtemp(prefix='omni_')
    entries = []
    for i, (t0, t1, text) in enumerate(cues):
        wav = os.path.join(tmp, f'{i:03d}.wav')
        t_start = time.time()
        synth(text, wav, voice, speed)
        d = dur_of(wav)
        slot = t1 - t0
        tempo = min(round(d / (slot + 0.1), 3), 2.6) if d > slot + 0.1 else 1.0
        entries.append((t0, wav, tempo))
        print(f'  #{i+1:02d} @{t0:7.2f} slot={slot:5.2f} gen={d:5.2f} tempo={tempo} ({time.time()-t_start:.0f}s)', flush=True)
    import subprocess
    n = len(entries)
    cmd = [FF, '-y', '-v', 'error']
    for _, wav, tempo in entries:
        cmd += ['-i', wav]
    fc = []
    for i, (_, _, tempo) in enumerate(entries):
        if tempo > 1.0:
            t = tempo; parts = []
            while t > 1.45: parts.append('1.45'); t /= 1.45
            parts.append(f'{t:.4f}')
            fc.append(f'[{i}:a]atempo=' + ',atempo='.join(parts) + f',aresample=48000[st{i}]')
        else:
            fc.append(f'[{i}:a]aresample=48000[st{i}]')
    for i, (t0, _, _) in enumerate(entries):
        fc.append(f'[st{i}]adelay={int(t0*1000)}|{int(t0*1000)}[s{i}]')
    fc.append(''.join(f'[s{i}]' for i in range(n)) +
              f'amix=inputs={n}:duration=longest:dropout_transition=0:normalize=0,volume=1.6[aout]')
    cmd += ['-filter_complex', ';'.join(fc), '-map', '[aout]', '-ar', '48000', '-ac', '2', outw]
    subprocess.run(cmd, check=True)
    print('OK ->', outw, f'{dur_of(outw):.2f}s')

if __name__ == '__main__':
    main()
