// Gemeinsame Bausteine fuer alle Sterne. Wird vom Renderer VOR allen spark_*.glsl eingefuegt.
// Koordinaten wie lab_spark.G: p = Zellmitte in m-Einheiten (m = kurze Seite), Ursprung oben links, y nach unten.

uniform vec2 uPage;        // Seite in m-Einheiten (A, B) = (W/m, H/m)
uniform vec2 uGrid;        // Zellraster (gw, gh)
uniform float uCell;       // Zellgroesse in m-Einheiten (= px / m)
uniform vec4 uStar;        // x0, y0, R (m-Einheiten), rot (Grad) -- Platzierung aus Editor/K
uniform float uSeed;
uniform sampler2D uProf;   // 3600x1 R32F: Sternradius (Spitze = 1) je 0.1 Grad, = makernight_sparks.PROF
uniform sampler2D uTitle;  // gw x gh R8: 1 = Titel-Glyphe (fuer Sterne, die mit dem Titel spielen)
uniform sampler2D uText;   // gw x gh R8: 1 = irgendeine Schrift (Titel, Datum, Meta, CTA)
uniform vec4 uTitleBox;    // Titel-Bbox in m: x0, y0, x1, y1

bool tall() { return uPage.y > uPage.x; }

// makernight_sparks.star_r: Radius in Richtung d (atan2 mit y nach unten, wie numpy), rot in Grad
float star_r(vec2 d, float rot) {
  float a = mod(degrees(atan(d.y, d.x)) - rot, 360.0) * 10.0;
  int i = int(floor(a));
  float f = a - float(i);
  return mix(texelFetch(uProf, ivec2(i % 3600, 0), 0).r, texelFetch(uProf, ivec2((i + 1) % 3600, 0), 0).r, f);
}
// lab_spark.sd / star: normierte Sterndistanz, 1 = Umriss
float sd(vec2 d, float rot) { return length(d) / max(star_r(d, rot), 1e-6); }
float star(vec2 p, float x0, float y0, float R, float rot) { return sd(p - vec2(x0, y0), rot) / R; }
float starMain(vec2 p) { return star(p, uStar.x, uStar.y, uStar.z, uStar.w); }

// lab_spark.bg: ruhiger Seitenverlauf
float bg(vec2 p, float lo, float hi) {
  vec2 n = p / uPage;
  return lo + hi * (tall() ? n.y : (0.35 * n.x + n.y) / 1.35);
}
float bg(vec2 p) { return bg(p, 0.02, 0.07); }

// Rauschen (nicht bitgleich zu numpy, gleicher Charakter). s = Massstab in m, Rueckgabe grob [-1, 1]
float hash12(vec2 q) { vec3 p3 = fract(vec3(q.xyx) * 0.1031); p3 += dot(p3, p3.yzx + 33.33); return fract((p3.x + p3.y) * p3.z); }
float vnoise(vec2 q) {
  vec2 i = floor(q), f = fract(q), u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash12(i), hash12(i + vec2(1, 0)), u.x), mix(hash12(i + vec2(0, 1)), hash12(i + vec2(1, 1)), u.x), u.y);
}
float fbm(vec2 p, float s, float seed) {
  float acc = 0.0, tot = 0.0, a = 1.0;
  vec2 q = p / s + seed * 17.13;
  for (int o = 0; o < 4; o++) { acc += a * vnoise(q); tot += a; q = q * 2.0 + 5.2; a *= 0.5; }
  return clamp((acc / tot - 0.5) * 3.2, -1.0, 1.0);
}
float titleMask(vec2 p) { return texelFetch(uTitle, ivec2(clamp(p / uCell, vec2(0), uGrid - 1.0)), 0).r; }
float textMask(vec2 p) { return texelFetch(uText, ivec2(clamp(p / uCell, vec2(0), uGrid - 1.0)), 0).r; }
