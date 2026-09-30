// default: 0.56 1.02 0.44 14
// default-wide: 1.22 0.56 0.44 14
// S40 Verkohlung (lab_spark.c_verkohlung): Gray-Scott-Labyrinth im Stern, am Rand Punkte, die nach aussen absterben.
// Ohne Simulation: schmalbandiges Rauschen (Summe ebener Wellen gleicher Wellenlaenge, leicht verwirbelt) mit
// Schwelle. Niedrige Schwelle = Labyrinth mit Verzweigungen, hohe Schwelle = isolierte Punkte, noch hoeher = tot.
float S40_band(vec2 x) {
  float acc = 0.0;
  for (int i = 0; i < 24; i++) {
    float fi = float(i);
    float a = fi * 3.14159265 / 24.0 + 0.10 * (hash12(vec2(fi, 40.0 + uSeed)) - 0.5);
    float ph = 6.2831853 * hash12(vec2(fi, 41.7 + uSeed));
    acc += cos(dot(vec2(cos(a), sin(a)), x) + ph);
  }
  return acc / sqrt(12.0);                                // ~ Einheitsvarianz
}
// Labyrinth als Hoehenlinien eines glatten Feldes Phi (wie Maserung/Fingerabdruck). Linienbreite ueber den
// Abstand zur naechsten Hoehenlinie (fract(Phi/P) / |grad Phi|), damit sie ueberall gleich dick ist.
float S40_phi(vec2 q, float R) {                         // glatt: 6 Wellen ~1.1 R + 4 Wellen ~0.5 R gegen Regelmass
  float k = 6.2831853 / (1.1 * R), k2 = 6.2831853 / (0.5 * R), a1 = 0.0, a2 = 0.0;
  for (int i = 0; i < 6; i++) {
    float fi = float(i);
    float a = fi * 0.5236 + 0.4 * hash12(vec2(fi, 404.0 + uSeed));
    a1 += sin(k * dot(vec2(cos(a), sin(a)), q) + 6.2831853 * hash12(vec2(fi, 405.0 + uSeed)));
    if (i < 4) {
      float b = fi * 0.785 + 0.6 * hash12(vec2(fi, 406.0 + uSeed));
      a2 += sin(k2 * dot(vec2(cos(b), sin(b)), q) + 6.2831853 * hash12(vec2(fi, 407.0 + uSeed)));
    }
  }
  return 2.6 * a1 / (k * 1.73) + 1.0 * a2 / (k2 * 1.41);
}
vec4 spark_S40(vec2 p) {
  float x0 = uStar.x, y0 = uStar.y, R = uStar.z, rot = uStar.w;
  float d = star(p, x0, y0, R, rot);
  vec2 q = p - vec2(x0, y0);
  float c = cos(radians(rot)), s = sin(radians(rot));
  q = mat2(c, -s, s, c) * q;                              // Muster dreht mit dem Stern
  // Labyrinth: Streifen mit Periode 0.125 R (wie im 300er-RD-Raster), helle Linie ~ 1/3 der Periode
  float e = 0.01 * R, P = 0.11 * R;                       // P = Linienabstand wie im 300er-RD-Raster
  float f0 = S40_phi(q, R);
  vec2 gr = vec2(S40_phi(q + vec2(e, 0), R) - f0, S40_phi(q + vec2(0, e), R) - f0) / e;
  float gl = max(length(gr), 1e-3);
  // Hoehenlinien-Abstand schwankt mit gl: Periode in Phi in Zweierpotenzen (Ebene n+1 ist Teilmenge von n).
  // Die Zwischenlinien der feineren Ebene laufen spitz aus, wo gl sinkt -> Linienenden und Gabeln wie im RD.
  float lg = log2(gl) + 0.5, fn = floor(lg), fade = smoothstep(0.0, 0.25, 1.0 - fract(lg));
  float per = P * exp2(fn);
  float d1 = abs(fract(f0 / per + 0.5) - 0.5) * per / gl;           // feine Ebene
  float d2 = abs(fract(f0 / (2.0 * per) + 0.5) - 0.5) * 2.0 * per / gl;  // grobe Ebene
  float line = max(1.0 - smoothstep(0.012 * R, 0.030 * R, d2),
                   1.0 - smoothstep(0.012 * R * fade, 0.030 * R * fade + 1e-5, d1));
  // Punkte = Gipfel eines zweiten Bandrauschens, Schwelle steigt nach aussen (Punkte sterben ab)
  float Pd = S40_band(mat2(0.8, 0.6, -0.6, 0.8) * q * 6.2831853 / (0.13 * R) + 11.0);
  float die = clamp((d - 1.25) / 0.3, 0.0, 1.0);
  float t = 0.85 + 2.2 * die;
  float dot_ = smoothstep(t, t + 0.5, Pd);
  float w = smoothstep(0.88, 1.02, d);                    // Labyrinth -> Punkte am Umriss
  float pat = d > 1.6 ? 0.0 : mix(line, dot_, w);
  float v = d < 1.0 ? 0.18 + 0.82 * pat : bg(p) + 0.1 * exp(-max(d - 1.0, 0.0) / 0.3) + 0.7 * pat;
  bool lit = d < 1.0 && pat > 0.5;
  return vec4(clamp(v, 0.0, 1.0), lit ? 1.0 : 0.0, 0.0, 0.0);
}
