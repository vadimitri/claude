// default: Tx Ty-0.0158 0.2177 14
// default-wide: Tx Ty-0.0304 0.3083 14
// S31d "Randlicht" (lab_spark.c_randlicht): Buchstaben als schwarze Koerper vor dem Stern, harte Lichtkante wo das Licht
// ihre Kanten streift, dazu weiche Schaechte. Default = _behind(bb) (Ty - 0.10 h; Offset und R aus dem Kick-off-Titel, h = Titelhoehe).
float S31d_ink(float d, float lo) { return lo + (1.0 - lo) * pow(clamp(1.0 - d, 0.0, 1.0), 0.7); }

// f-Intervall der Strecke c + (p - c) f (f in [0, 1]) innerhalb der Titel-Bbox (+2 Zellen): nur dort kann Schrift verdecken
vec2 S31d_clip(vec2 p, vec2 c) {
  vec2 dir = p - c;
  dir = mix(dir, vec2(1e-6), lessThan(abs(dir), vec2(1e-6)));
  vec4 b = uTitleBox + vec4(-2.0, -2.0, 2.0, 2.0) * uCell;
  vec2 t1 = (b.xy - c) / dir, t2 = (b.zw - c) / dir;
  vec2 lo = min(t1, t2), hi = max(t1, t2);
  return vec2(max(max(lo.x, lo.y), 0.0), min(min(hi.x, hi.y), 1.0));
}

// lab_spark._lit_band (Plakatmodus): im Titel-/Datumsband kippt Schrift ab v >= 0.2, die Kopfzeile erst ab 0.5
float S31d_litBand(vec2 p, float v) { return (p.y > uTitleBox.y - 0.025 ? v >= 0.2 : v >= 0.5) ? 1.0 : 0.0; }

// lab_spark.shafts: mittlere Emission auf der Strecke p -> Stern (emit = 1 im Stern, aussen 0.6 exp(-(d-1)/0.25)),
// Schrift schneidet die Emission weg. Unverdeckter Teil analytisch, die Schrift wird in <= 48 Schritten abgezogen.
// Normierung: 90. Perzentil im Ring d 1..1.3 ~ 0.97.
float S31d_emit(float x) { return x < 1.0 ? 1.0 : 0.6 * exp(-(x - 1.0) / 0.25); }
float S31d_shafts(vec2 p, vec2 c, float d, float gamma) {
  float full = d <= 1.0 ? 1.0 : (1.0 + 0.15 * (1.0 - exp(-(d - 1.0) / 0.25))) / d;
  vec2 fr = S31d_clip(p, c);
  float occ = 0.0;
  if (fr.y > fr.x) {
    float df = (fr.y - fr.x) / 48.0;
    for (int i = 0; i < 48; i++) {
      float f = fr.x + (float(i) + 0.5) * df;
      occ += titleMask(c + (p - c) * f) * S31d_emit(f * d);
    }
    occ *= df;
  }
  return pow(clamp((full - occ) / 0.97, 0.0, 1.2), gamma);
}

// Harter Schatten: liegt zwischen p und dem Stern (ausserhalb des Sterns) ein Titelpixel? (radial(T & d >= 1) >= 0.5)
bool S31d_shadow(vec2 p, vec2 c, float d) {
  vec2 fr = S31d_clip(p, c);
  fr.x = max(fr.x, 1.0 / max(d, 1e-6));
  if (fr.y <= fr.x) return false;
  float df = (fr.y - fr.x) / 48.0;
  for (int i = 0; i < 48; i++)
    if (titleMask(c + (p - c) * (fr.x + (float(i) + 0.5) * df)) > 0.5) return true;
  return false;
}

vec4 spark_S31d(vec2 p) {
  vec2 c = uStar.xy;
  float R = uStar.z;
  float d = starMain(p);
  float r = length(p - c);
  // rim(): Zelle vor einem Buchstaben auf der Lichtseite (n Zellen weiter vom Stern weg liegt Schrift)
  bool rl = false;
  if (titleMask(p) < 0.5 && r > 1e-6) {
    vec2 st = floor((p - c) / r + 0.5) * uCell;             // np.round auf -1/0/1 Zellen
    int n = max(1, int(floor(1.0 / (uCell * 260.0) + 0.5)));
    for (int k = 1; k <= 4; k++)
      if (k <= n && titleMask(p + float(k) * st) > 0.5) rl = true;
    rl = rl && !S31d_shadow(p, c, d);                       // nur wo Licht hinkommt
  }
  float hot = exp(-max(r - R, 0.0) / (0.9 * R));
  float v = bg(p, 0.0, 0.04) + 0.85 * S31d_shafts(p, c, d, 0.8);
  if (d < 1.0) v = S31d_ink(d, 0.8);
  if (rl) v = hot > 0.35 ? 1.0 : max(v, 0.35 + 0.6 * hot);
  v = clamp(v, 0.0, 1.0);
  return vec4(v, S31d_litBand(p, v), 0.0, 0.0);
}
