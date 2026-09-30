// default: 0.50 0.84 0.46 14
// default-wide: 1.28 0.50 0.46 14
// S14 Attraktor (lab_spark.c_attraktor): Chaos-Spiel mit 12 Kontraktionen (s = 0.3, 11 Grad Drall) zu den Spitzen.
// Statt Punkte zu streuen: inverses IFS. Dichte ~ Zahl der Adresspfade der Laenge L, deren Urbilder alle im
// Einheitskreis (Huelle des Attraktors) bleiben. L so, dass s^L * R etwa eine Zelle ist (= Histogrammraster).
vec4 spark_S14(vec2 p) {
  float R = uStar.z, rot = uStar.w;
  const float s = 0.30;
  float tw = radians(11.0), ct = cos(tw), st = sin(tw);
  vec2 T[12];
  for (int k = 0; k < 6; k++) {
    float a = radians(rot + 30.0 + 60.0 * float(k));
    T[k] = vec2(cos(a), sin(a)) * (1.0 - s);
    T[k + 6] = 0.42 * vec2(cos(a - 0.5235988), sin(a - 0.5235988)) * (1.0 - s);
  }
  vec2 q0 = (p - uStar.xy) / R;
  int L = clamp(int(ceil(log(uCell / R) / log(s))), 2, 5);
  vec2 qs[6]; int ks[6];
  qs[0] = q0; ks[0] = 0;
  int l = 0;
  float N = 0.0, halo = 0.0;
  if (length(q0) > 1.0) l = -1;
  for (int it = 0; it < 900; it++) {
    if (l < 0) break;
    if (l == L) { N += 1.0; l--; continue; }
    if (ks[l] >= 12) { l--; continue; }
    int k = ks[l]++;
    vec2 e = qs[l] - T[k];
    if (dot(e, e) > s * s) continue;
    vec2 q = vec2(ct * e.x + st * e.y, -st * e.x + ct * e.y) / s;   // Rm^-1 (q - T)
    l++;
    qs[l] = q; ks[l] = 0;
    if (l == 2) halo += 1.0 - dot(q, q);
  }
  // Halo (numpy: Gauss ueber das Histogramm): weiche Ebene-1-Dichte, reicht etwas ueber den Attraktor hinaus
  float h1 = 0.0;
  for (int k = 0; k < 12; k++) {
    vec2 e = (q0 - T[k]) / s;
    h1 += exp(-dot(e, e) * 0.9);
  }
  float H = sqrt(N / 5.0);
  float v = bg(p) + 0.3 * clamp(0.16 * h1 + 0.08 * halo, 0.0, 1.0) + 0.85 * pow(clamp(H, 0.0, 1.0), 1.3);
  v = clamp(v, 0.0, 1.0);
  return vec4(v, v >= 0.5 ? 1.0 : 0.0, 0.0, 0.0);
}
