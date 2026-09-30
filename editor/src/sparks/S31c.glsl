// default: Tx Ty-0.0158 0.2975 14
// default-wide: Tx Ty-0.0304 0.4437 14
// S31c "Zweitlicht" (lab_spark.c_zweitlicht): Stern + Titelsilhouette in der eigenen Palette, die Schaechte dahinter
// in der Zweitpalette (v2/a2). Default = _behind(bb) mit R = h + 0.14 (Ty - 0.10 h; Offset und R aus dem Kick-off-Titel, h = Titelhoehe).
float S31c_ink(float d, float lo) { return lo + (1.0 - lo) * pow(clamp(1.0 - d, 0.0, 1.0), 0.7); }

// f-Intervall der Strecke c + (p - c) f (f in [0, 1]) innerhalb der Titel-Bbox (+2 Zellen): nur dort kann Schrift verdecken
vec2 S31c_clip(vec2 p, vec2 c) {
  vec2 dir = p - c;
  dir = mix(dir, vec2(1e-6), lessThan(abs(dir), vec2(1e-6)));
  vec4 b = uTitleBox + vec4(-2.0, -2.0, 2.0, 2.0) * uCell;
  vec2 t1 = (b.xy - c) / dir, t2 = (b.zw - c) / dir;
  vec2 lo = min(t1, t2), hi = max(t1, t2);
  return vec2(max(max(lo.x, lo.y), 0.0), min(min(hi.x, hi.y), 1.0));
}

// lab_spark._lit_band (Plakatmodus): im Titel-/Datumsband kippt Schrift ab v >= 0.2, die Kopfzeile erst ab 0.5
float S31c_litBand(vec2 p, float v) { return (p.y > uTitleBox.y - 0.025 ? v >= 0.2 : v >= 0.5) ? 1.0 : 0.0; }

// lab_spark.shafts: mittlere Emission auf der Strecke p -> Stern (emit = 1 im Stern, aussen 0.6 exp(-(d-1)/0.25)),
// Schrift schneidet die Emission weg. Unverdeckter Teil analytisch, die Schrift wird in <= 48 Schritten abgezogen.
// Normierung: 90. Perzentil im Ring d 1..1.3 ~ 0.97.
float S31c_emit(float x) { return x < 1.0 ? 1.0 : 0.6 * exp(-(x - 1.0) / 0.25); }
float S31c_shafts(vec2 p, vec2 c, float d, float gamma) {
  float full = d <= 1.0 ? 1.0 : (1.0 + 0.15 * (1.0 - exp(-(d - 1.0) / 0.25))) / d;
  vec2 fr = S31c_clip(p, c);
  float occ = 0.0;
  if (fr.y > fr.x) {
    float df = (fr.y - fr.x) / 48.0;
    for (int i = 0; i < 48; i++) {
      float f = fr.x + (float(i) + 0.5) * df;
      occ += titleMask(c + (p - c) * f) * S31c_emit(f * d);
    }
    occ *= df;
  }
  return pow(clamp((full - occ) / 0.97, 0.0, 1.2), gamma);
}

vec4 spark_S31c(vec2 p) {
  float d = starMain(p);
  float rays = S31c_shafts(p, uStar.xy, d, 0.75);
  bool st = d < 1.0;
  float v = st ? S31c_ink(d, 0.8) : 0.0;
  float v2 = clamp(0.01 + 0.97 * rays, 0.0, 1.0);
  return vec4(v, S31c_litBand(p, st ? 1.0 : rays), v2, st ? 0.0 : 1.0);   // Schrift nimmt CORE aus a2 heraus
}
