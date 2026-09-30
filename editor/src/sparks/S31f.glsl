// default: Tx Ty-0.0158 0.2177 14
// default-wide: Tx Ty-0.0304 0.3083 14
// S31f "Strahlenkranz" (lab_spark.c_strahlenkranz): 24 harte Lichtkeile vom Stern hinter dem Titel ueber die ganze Seite,
// die Buchstaben werfen ihre Schatten hinein. Default = _behind(bb) (Ty - 0.10 h; Offset und R aus dem Kick-off-Titel, h = Titelhoehe).
float S31f_ink(float d, float lo) { return lo + (1.0 - lo) * pow(clamp(1.0 - d, 0.0, 1.0), 0.7); }

// f-Intervall der Strecke c + (p - c) f (f in [0, 1]) innerhalb der Titel-Bbox (+2 Zellen): nur dort kann Schrift verdecken
vec2 S31f_clip(vec2 p, vec2 c) {
  vec2 dir = p - c;
  dir = mix(dir, vec2(1e-6), lessThan(abs(dir), vec2(1e-6)));
  vec4 b = uTitleBox + vec4(-2.0, -2.0, 2.0, 2.0) * uCell;
  vec2 t1 = (b.xy - c) / dir, t2 = (b.zw - c) / dir;
  vec2 lo = min(t1, t2), hi = max(t1, t2);
  return vec2(max(max(lo.x, lo.y), 0.0), min(min(hi.x, hi.y), 1.0));
}

// lab_spark._lit_band (Plakatmodus): im Titel-/Datumsband kippt Schrift ab v >= 0.2, die Kopfzeile erst ab 0.5
float S31f_litBand(vec2 p, float v) { return (p.y > uTitleBox.y - 0.025 ? v >= 0.2 : v >= 0.5) ? 1.0 : 0.0; }

// Harter Schatten: liegt zwischen p und dem Stern (ausserhalb des Sterns) ein Titelpixel? (radial(T & d >= 1) >= 0.5)
bool S31f_shadow(vec2 p, vec2 c, float d) {
  vec2 fr = S31f_clip(p, c);
  fr.x = max(fr.x, 1.0 / max(d, 1e-6));
  if (fr.y <= fr.x) return false;
  float df = (fr.y - fr.x) / 48.0;
  for (int i = 0; i < 48; i++)
    if (titleMask(c + (p - c) * (fr.x + (float(i) + 0.5) * df)) > 0.5) return true;
  return false;
}

vec4 spark_S31f(vec2 p) {
  vec2 c = uStar.xy;
  float R = uStar.z;
  float d = starMain(p);
  vec2 q = p - c;
  float r = length(q);
  float th = atan(q.y, q.x) - radians(uStar.w);
  float wob = 0.5 + 0.5 * cos(24.0 * th + 0.9 * sin(3.0 * th));
  float beam = clamp((wob - 0.35) / 0.4, 0.0, 1.0);
  float vis = S31f_shadow(p, c, d) ? 0.0 : 1.0;
  float I = beam * exp(-max(r - R, 0.0) / (0.95 * uPage.y)) * vis;
  float halo = exp(-max(r - R, 0.0) / 0.35);                          // Glut hinter der Zeile, damit die Silhouette steht
  float v = bg(p, 0.0, 0.03) + 0.62 * I + 0.45 * halo;
  if (d < 1.0) v = S31f_ink(d, 0.8);
  v = clamp(v, 0.0, 1.0);
  return vec4(v, v >= 0.45 ? 1.0 : 0.0, 0.0, 0.0);                   // per_pixel
}
