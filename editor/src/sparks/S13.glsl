// default: 0.60 0.98 0.25 14
// default-wide: 1.30 0.52 0.30 14
// S13 Sternkind (lab_spark.c_sternkind): jede Spitze gebiert einen kleineren Stern (0.42x, 5 Ebenen), XOR-Paritaet.
// Rekursion als DFS mit eigenem Stack; Teilbaeume, deren Huelle (1.8 r) p nicht erreicht, werden uebersprungen.
vec4 spark_S13(vec2 p) {
  float x0 = uStar.x, y0 = uStar.y, R = uStar.z, rot = uStar.w;
  vec2 cs[6]; float rs[6]; float bs[6]; int ks[6];
  cs[0] = vec2(x0, y0); rs[0] = R; bs[0] = -99.0; ks[0] = 0;
  bool acc = sd(p - cs[0], rot) < R;
  if (length(p - cs[0]) > 1.8 * R) ks[0] = 6;
  int l = 0;
  for (int it = 0; it < 400; it++) {
    if (l < 0) break;
    if (ks[l] >= 6 || l == 5) { l--; continue; }
    int k = ks[l]++;
    float a = radians(rot + 30.0 + 60.0 * float(k));
    if (bs[l] > -90.0 && cos(a - bs[l]) <= 0.4) continue;       // nur nach aussen wachsen
    vec2 c = cs[l] + vec2(cos(a), sin(a)) * rs[l] * 1.02;
    float r = rs[l] * 0.42;
    if (length(p - c) > 1.8 * r) continue;                       // Teilbaum erreicht p nicht
    if (sd(p - c, rot) < r) acc = !acc;
    l++;
    cs[l] = c; rs[l] = r; bs[l] = a; ks[l] = 0;
  }
  float d = star(p, x0, y0, R * 1.5, rot);
  float v = bg(p) + 0.10 * exp(-max(d - 1.0, 0.0) / 0.4);
  if (acc) v = 0.6 + 0.4 * pow(clamp(1.0 - d, 0.0, 1.0), 0.7);
  return vec4(v, acc ? 1.0 : 0.0, 0.0, 0.0);
}
