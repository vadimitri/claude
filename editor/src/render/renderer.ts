// WebGL2-Renderer: Pass 1 = Seitenhintergrund + Spark + QR -> RGBA32F (V, lit, v2, a2), Pass 2 = Schrift/Flip,
// Zweitlicht, Bayer 4x4 und Palette -> Canvas im Zellraster (gw x gh). Anzeige skaliert die UI per CSS (pixelated).
import type { Scene } from './types';
import data from '../data.json';
import common from '../sparks/_common.glsl?raw';

export type { Scene } from './types';

const files = import.meta.glob('../sparks/*.glsl', { query: '?raw', import: 'default', eager: true }) as Record<string, string>;

// Spark-Quellen: Code -> GLSL (ohne _common)
const SOURCES: Record<string, string> = {};
for (const [path, src] of Object.entries(files)) {
  const code = path.split('/').pop()!.replace(/\.glsl$/, '');
  if (!code.startsWith('_')) SOURCES[code] = src;
}

// Rueckfall, wenn kein Spark kompiliert oder der Code fehlt: S2-Verlauf aus styles.spark
const FALLBACK = `vec4 sparkFallback(vec2 p) {
  float d = starMain(p);
  return d < 1.0 ? vec4(0.64 + 0.36 * pow(clamp(1.0 - d, 0.0, 1.0), 0.7), 1.0, 0.0, 0.0) : vec4(-1.0, 0.0, 0.0, 0.0);
}`;

const NUM = String.raw`((?:Tx|Ty|-?[\d.]+[AB]?)(?:[+-][\d.]+)?)`;
const LINE = (tag: string) => new RegExp(String.raw`^\s*//\s*${tag}:\s*` + [NUM, NUM, NUM, NUM].join(String.raw`\s+`) + String.raw`(.*)$`, 'm');

/** OWN-Default aus der Spark-Datei, passend zum Format. page = uPage (A, B) = (W/m, H/m), titleBox in m (x0, y0, x1, y1).
 *  `// default: x0 y0 R rot` = hochkant, optional `// default-wide: ...` = quer (sonst gilt `default` auch quer).
 *  Token: reine Zahl = m-Einheiten, `0.5A` = 0.5 * A, `0.63B` = 0.63 * B, `Tx`/`Ty` = Titelmitte; jeweils mit
 *  optionalem Offset in m (`Ty+0.016`). Ohne titleBox gilt die Seitenmitte als Titelmitte.
 *  Altform `// default: <quer> (hoch: <hoch>)` wird weiter verstanden. */
export function sparkDefault(code: string, page: [number, number] = [1, 1],
                             titleBox?: [number, number, number, number]): [number, number, number, number] | null {
  const src = SOURCES[code];
  if (!src) return null;
  const [A, B] = page, tall = B > A;
  const [tx, ty] = titleBox ? [(titleBox[0] + titleBox[2]) / 2, (titleBox[1] + titleBox[3]) / 2] : [A / 2, B / 2];
  const val = (t: string) => {
    const m = t.match(/^(Tx|Ty|-?[\d.]+[AB]?)([+-][\d.]+)?$/)!;
    const b = m[1], off = m[2] ? parseFloat(m[2]) : 0;
    const base = b === 'Tx' ? tx : b === 'Ty' ? ty : b.endsWith('A') ? parseFloat(b) * A : b.endsWith('B') ? parseFloat(b) * B : parseFloat(b);
    return base + off;
  };
  const four = (m: string[]) => [val(m[0]), val(m[1]), val(m[2]), val(m[3])] as [number, number, number, number];
  const d = src.match(LINE('default')), w = src.match(LINE('default-wide'));
  if (!d && !w) return null;
  const legacy = d?.[5].match(new RegExp(String.raw`\(hoch:\s*` + [NUM, NUM, NUM, NUM].join(String.raw`\s+`) + String.raw`\s*\)`));
  if (legacy && !w) return tall ? four(legacy.slice(1)) : four(d!.slice(1));
  if (!tall && w) return four(w.slice(1));
  return four((d ?? w)!.slice(1));
}

const HEAD = `#version 300 es
precision highp float;
precision highp int;
precision highp sampler2D;
`;

const VERT = `#version 300 es
void main() {
  vec2 v = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));
  gl_Position = vec4(v * 2.0 - 1.0, 0.0, 1.0);
}`;

function pass1Source(codes: string[]): string {
  const calls = codes.map((c, i) => `  if (uSpark == ${i}) return spark_${c}(p);`).join('\n');
  return `${HEAD}
uniform int uSpark;
uniform float uGlow;
uniform vec4 uQr;      // x, y, n (Zellen, n = 0: kein QR), qn (Module)
uniform vec4 uQrLv;    // hi, hi2, lo, amt
uniform sampler2D uQrMod;
out vec4 fragOut;
${common}
${codes.map((c) => `// ---- ${c}\n${SOURCES[c]}`).join('\n')}
${FALLBACK}
vec4 sparkEval(vec2 p) {
${calls}
  return sparkFallback(p);
}
void main() {
  ivec2 c = ivec2(int(gl_FragCoord.x), int(uGrid.y) - 1 - int(gl_FragCoord.y));  // Zeile von oben
  vec2 cf = vec2(c) + 0.5;
  vec2 p = cf * uCell;
  // styles.background: Verlauf + Nebel + Glow um den Stern
  vec2 nn = cf / uGrid;
  float grad = tall() ? nn.y : (0.35 * nn.x + nn.y) / 1.35;
  float V = 0.025 + 0.085 * pow(max(grad, 0.0), 1.3) + 0.02 * fbm(p, 44.0 * uCell, 26.0);
  if (uGlow > 0.5) {
    float d = starMain(p);
    float rr = length(p - uStar.xy) / uStar.z;
    if (d > 1.0) V += 0.15 * exp(-(d - 1.0) / 0.3) + 0.16 * exp(-rr / 1.6);
  }
  vec4 s = sparkEval(p);
  if (s.x >= 0.0) V = clamp(s.x, 0.0, 1.0);
  float a2 = s.w;
  // kickoff.qr: Halo, Platte, Module
  if (uQr.z > 0.0) {
    vec2 q = vec2(c) - uQr.xy;
    float n = uQr.z;
    float dx = max(max(-q.x, q.x - (n - 1.0)), 0.0), dy = max(max(-q.y, q.y - (n - 1.0)), 0.0);
    float dist = length(vec2(dx, dy)) / 2.0;
    if (dist > 0.0 && dist < 10.0) { V = clamp(V + (uQrLv.x - V) * exp(-dist / 2.6), 0.0, 1.0); a2 = 0.0; }
    if (q.x >= 0.0 && q.x < n && q.y >= 0.0 && q.y < n) {
      V = uQrLv.x + (uQrLv.y - uQrLv.x) * uQrLv.w * clamp((q.x + q.y) / (2.0 * n), 0.0, 1.0);
      a2 = 0.0;
      ivec2 mi = (ivec2(q) - 6) / 2;
      if (all(greaterThanEqual(ivec2(q) - 6, ivec2(0))) && all(lessThan(mi, ivec2(int(uQr.w)))) &&
          texelFetch(uQrMod, mi, 0).r > 0.5) V = uQrLv.z;
    }
  }
  fragOut = vec4(V, s.y, s.z, a2);
}`;
}

const PASS2 = `${HEAD}
uniform sampler2D uBase;   // Pass 1, GL-Orientierung
uniform sampler2D uTypeV;  // R32F, -1 = keine Schrift
uniform sampler2D uFlip;   // R8: 1 = kippen wo lit, 2 = Glyphe kippt
uniform vec2 uGrid;
uniform vec3 uPal[16];
uniform int uN;
uniform vec3 uAlt[16];
uniform int uNAlt;
out vec4 fragOut;
const float BAYER[16] = float[16](0.0, 8.0, 2.0, 10.0, 12.0, 4.0, 14.0, 6.0, 3.0, 11.0, 1.0, 9.0, 15.0, 7.0, 13.0, 5.0);
int dith(float v, int N, ivec2 c) {       // styles.dither, bayer4
  float x = clamp(v, 0.0, 1.0) * float(N) + 1e-4;
  float lo = floor(x);
  float t = (BAYER[(c.y & 3) * 4 + (c.x & 3)] + 0.5) / 16.0;
  return clamp(int(lo) + (x - lo > t ? 1 : 0), 0, N);
}
void main() {
  ivec2 g = ivec2(gl_FragCoord.xy);
  ivec2 c = ivec2(g.x, int(uGrid.y) - 1 - g.y);
  vec4 b = texelFetch(uBase, g, 0);
  float tv = texelFetch(uTypeV, c, 0).r;
  vec3 col;
  if (tv >= 0.0) {
    int f = int(texelFetch(uFlip, c, 0).r * 255.0 + 0.5);
    if ((f == 1 && b.y > 0.5) || f == 2) tv = 0.0;
    col = uPal[dith(tv, uN, c)];
  } else if (b.w > 0.5 && uNAlt > 0) {
    col = uAlt[dith(b.z, uNAlt, c)];
  } else {
    col = uPal[dith(b.x, uN, c)];
  }
  fragOut = vec4(col / 255.0, 1.0);
}`;

function hexRGB(h: string): [number, number, number] {
  const n = parseInt(h.replace('#', ''), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}
function palArray(p: string[]): Float32Array {
  const a = new Float32Array(48);
  p.slice(0, 16).forEach((h, i) => a.set(hexRGB(h), i * 3));
  return a;
}
const lum = (h: string) => { const [r, g, b] = hexRGB(h); return 0.2126 * r + 0.7152 * g + 0.0722 * b; };

type Prog = { prog: WebGLProgram; loc: Record<string, WebGLUniformLocation | null> };

export class Renderer {
  readonly gl: WebGL2RenderingContext;
  errors: { code: string; log: string }[] = [];
  private codes: string[] = [];
  private p1!: Prog;
  private p2!: Prog;
  private tex: Record<string, WebGLTexture> = {};
  private fbo: WebGLFramebuffer;
  private fboSize = [0, 0];
  private cache = new Map<string, unknown>();      // Textur -> zuletzt hochgeladenes Array (Identitaet)
  private readBuf = new Float32Array(0);
  private flipBuf = new Uint8Array(0);

  constructor(readonly canvas: HTMLCanvasElement) {
    const gl = canvas.getContext('webgl2', { antialias: false, alpha: false, preserveDrawingBuffer: false });
    if (!gl) throw new Error('WebGL2 nicht verfuegbar');
    if (!gl.getExtension('EXT_color_buffer_float')) throw new Error('EXT_color_buffer_float fehlt');
    this.gl = gl;
    gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
    gl.pixelStorei(gl.PACK_ALIGNMENT, 1);
    this.build();
    this.p2 = this.link(PASS2)!;
    for (const k of ['base', 'prof', 'title', 'text', 'typeV', 'flip', 'qr']) this.tex[k] = this.newTex();
    const prof = new Float32Array(data.prof as number[]);
    this.upload('prof', gl.R32F, gl.RED, gl.FLOAT, prof.length, 1, prof);
    this.fbo = gl.createFramebuffer()!;
  }

  /** Verfuegbare (kompilierte) Spark-Codes. */
  sparkCodes(): string[] { return [...this.codes]; }

  private newTex(): WebGLTexture {
    const gl = this.gl, t = gl.createTexture()!;
    gl.bindTexture(gl.TEXTURE_2D, t);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
    gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
    return t;
  }
  private upload(k: string, ifmt: number, fmt: number, type: number, w: number, h: number, px: ArrayBufferView | null) {
    const gl = this.gl;
    gl.bindTexture(gl.TEXTURE_2D, this.tex[k]);
    gl.texImage2D(gl.TEXTURE_2D, 0, ifmt, w, h, 0, fmt, type, px);
  }
  private shader(type: number, src: string): WebGLShader {
    const gl = this.gl, s = gl.createShader(type)!;
    gl.shaderSource(s, src);
    gl.compileShader(s);
    return s;
  }
  private link(fs: string, tag = 'pass'): Prog | null {
    const gl = this.gl, prog = gl.createProgram()!;
    const v = this.shader(gl.VERTEX_SHADER, VERT), f = this.shader(gl.FRAGMENT_SHADER, fs);
    gl.attachShader(prog, v); gl.attachShader(prog, f); gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
      const log = (gl.getShaderInfoLog(f) || '') + (gl.getProgramInfoLog(prog) || '');
      this.errors.push({ code: tag, log });
      console.error(`[renderer] ${tag}:`, log);
      return null;
    }
    const loc: Prog['loc'] = {};
    const n = gl.getProgramParameter(prog, gl.ACTIVE_UNIFORMS);
    for (let i = 0; i < n; i++) {
      const name = gl.getActiveUniform(prog, i)!.name.replace(/\[0\]$/, '');
      loc[name] = gl.getUniformLocation(prog, name);
    }
    return { prog, loc };
  }

  /** Jeden Spark einzeln testkompilieren (parallel), nur die guten ins Programm. */
  private build() {
    const gl = this.gl;
    const all = Object.keys(SOURCES).sort((a, b) => a.localeCompare(b, 'en', { numeric: true }));
    const tests = all.map((c) => [c, this.shader(gl.FRAGMENT_SHADER, pass1Source([c]))] as const);
    const ok: string[] = [];
    for (const [c, s] of tests) {
      if (gl.getShaderParameter(s, gl.COMPILE_STATUS)) ok.push(c);
      else {
        const log = gl.getShaderInfoLog(s) || '';
        this.errors.push({ code: c, log });
        console.error(`[renderer] ${c} kompiliert nicht:\n${log}`);
      }
      gl.deleteShader(s);
    }
    let p = this.link(pass1Source(ok), 'all');
    if (!p) {                                            // Kollision zwischen Sparks: inkrementell aufbauen
      this.errors.pop();
      const keep: string[] = [];
      for (const c of ok) {
        const q = this.link(pass1Source([...keep, c]), c);
        if (q) { keep.push(c); gl.deleteProgram(q.prog); }
      }
      ok.splice(0, ok.length, ...keep);
      p = this.link(pass1Source(ok), 'all');
    }
    this.p1 = p ?? this.link(pass1Source([]), 'fallback')!;
    this.codes = p ? ok : [];
  }

  private sync(k: string, arr: unknown, fn: () => void) {
    if (this.cache.get(k) !== arr) { fn(); this.cache.set(k, arr); }
  }

  private mask(k: string, src: Uint8Array, w: number, h: number) {
    this.sync(k + w + 'x' + h, src, () => {
      const a = new Uint8Array(w * h);
      for (let i = 0; i < a.length; i++) a[i] = src[i] ? 255 : 0;
      this.upload(k, this.gl.R8, this.gl.RED, this.gl.UNSIGNED_BYTE, w, h, a);
    });
  }

  render(scene: Scene) {
    const gl = this.gl, { gw, gh } = scene;
    if (this.canvas.width !== gw || this.canvas.height !== gh) { this.canvas.width = gw; this.canvas.height = gh; }
    const m = Math.min(scene.W, scene.H);
    const ci = this.codes.indexOf(scene.spark);

    // Texturen
    if (this.fboSize[0] !== gw || this.fboSize[1] !== gh) {
      this.upload('base', gl.RGBA32F, gl.RGBA, gl.FLOAT, gw, gh, null);
      gl.bindFramebuffer(gl.FRAMEBUFFER, this.fbo);
      gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, this.tex.base, 0);
      this.fboSize = [gw, gh];
      this.cache.clear();
      this.readBuf = new Float32Array(gw * gh * 4);
      this.flipBuf = new Uint8Array(gw * gh);
    }
    this.mask('title', scene.titleMask, gw, gh);
    this.mask('text', scene.textMask, gw, gh);
    this.sync('typeV', scene.typeV, () => {
      const a = new Float32Array(gw * gh);
      for (let i = 0; i < a.length; i++) { const v = scene.typeV[i]; a[i] = Number.isNaN(v) || v === undefined ? -1 : v; }
      this.upload('typeV', gl.R32F, gl.RED, gl.FLOAT, gw, gh, a);
    });
    const qr = scene.qr;
    const qn = qr ? Math.round(Math.sqrt(qr.modules.length)) : 0;
    if (qr) this.mask('qr', qr.modules, qn, qn);

    // Pass 1
    gl.bindFramebuffer(gl.FRAMEBUFFER, this.fbo);
    gl.viewport(0, 0, gw, gh);
    const L1 = this.p1.loc;
    gl.useProgram(this.p1.prog);
    gl.uniform2f(L1.uPage, scene.W / m, scene.H / m);
    gl.uniform2f(L1.uGrid, gw, gh);
    gl.uniform1f(L1.uCell, scene.cellPx / m);
    gl.uniform4f(L1.uStar, ...scene.star);
    gl.uniform1f(L1.uSeed, scene.seed);
    gl.uniform4f(L1.uTitleBox, ...scene.titleBox);
    gl.uniform1i(L1.uSpark, ci);
    gl.uniform1f(L1.uGlow, scene.glow ? 1 : 0);
    const P = scene.pal, N = P.length - 1;
    const lums = P.map(lum);
    const ih = lums.indexOf(Math.max(...lums)), ilo = lums.indexOf(Math.min(...lums));
    const ih2 = ih === N ? ih - 1 : ih + 1;
    gl.uniform4f(L1.uQr, qr?.x ?? 0, qr?.y ?? 0, qr?.n ?? 0, qn);
    gl.uniform4f(L1.uQrLv, ih / N, ih2 / N, ilo / N, lums[ih2] > 0.55 * lums[ih] ? 0.55 : 0);
    const bind = (loc: WebGLUniformLocation | null | undefined, k: string, unit: number) => {
      gl.activeTexture(gl.TEXTURE0 + unit); gl.bindTexture(gl.TEXTURE_2D, this.tex[k]); gl.uniform1i(loc ?? null, unit);
    };
    bind(L1.uProf, 'prof', 0); bind(L1.uTitle, 'title', 1); bind(L1.uText, 'text', 2); bind(L1.uQrMod, 'qr', 3);
    gl.drawArrays(gl.TRIANGLES, 0, 3);

    // Kleintext: Mehrheit pro Glyphe (hell = lit oder Grund > 0.5), nur wenn es Flip-2-Zellen gibt
    const flip = this.flipBuf, F = scene.typeFlip;
    let needGlyph = false;
    for (let i = 0; i < flip.length; i++) { flip[i] = F[i] === 1 ? 1 : 0; if (F[i] === 2) needGlyph = true; }
    if (needGlyph) {
      const rb = this.readBuf;
      gl.readPixels(0, 0, gw, gh, gl.RGBA, gl.FLOAT, rb);
      const G = scene.glyphId;
      let nG = 0;
      for (let i = 0; i < G.length; i++) if (G[i] > nG) nG = G[i];
      const lit = new Float32Array(nG + 1), cnt = new Float32Array(nG + 1);
      for (let y = 0; y < gh; y++) {
        const r = (gh - 1 - y) * gw;                   // Readback-Zeile 0 = unten
        for (let x = 0; x < gw; x++) {
          const i = y * gw + x, g = G[i];
          if (!g || F[i] !== 2) continue;
          const j = (r + x) * 4;
          cnt[g]++; if (rb[j + 1] > 0.5 || rb[j] > 0.5) lit[g]++;
        }
      }
      for (let i = 0; i < flip.length; i++) if (F[i] === 2 && G[i] && lit[G[i]] > 0.5 * cnt[G[i]]) flip[i] = 2;
    }
    this.upload('flip', gl.R8, gl.RED, gl.UNSIGNED_BYTE, gw, gh, flip);

    // Pass 2
    gl.bindFramebuffer(gl.FRAMEBUFFER, null);
    gl.viewport(0, 0, gw, gh);
    const L2 = this.p2.loc;
    gl.useProgram(this.p2.prog);
    gl.uniform2f(L2.uGrid, gw, gh);
    gl.uniform3fv(L2.uPal, palArray(P));
    gl.uniform1i(L2.uN, N);
    gl.uniform3fv(L2.uAlt, palArray(scene.alt ?? []));
    gl.uniform1i(L2.uNAlt, scene.alt?.length ? scene.alt.length - 1 : 0);
    bind(L2.uBase, 'base', 0); bind(L2.uTypeV, 'typeV', 1); bind(L2.uFlip, 'flip', 2);
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  /** Volle Seite W x H als PNG, nearest-Upscale um cellPx. */
  async exportPNG(scene: Scene): Promise<Blob> {
    this.render(scene);
    const out = document.createElement('canvas');
    out.width = scene.W; out.height = scene.H;
    const ctx = out.getContext('2d')!;
    ctx.imageSmoothingEnabled = false;
    ctx.drawImage(this.canvas, 0, 0, scene.gw * scene.cellPx, scene.gh * scene.cellPx);  // gleicher Task wie render()
    return new Promise((res, rej) => out.toBlob((b) => (b ? res(b) : rej(new Error('toBlob fehlgeschlagen'))), 'image/png'));
  }
}

/** Codes, die kompilieren (braucht einen Renderer; ohne: alle vorhandenen Dateien). */
export function sparkCodes(r?: Renderer): string[] {
  return r ? r.sparkCodes() : Object.keys(SOURCES);
}
