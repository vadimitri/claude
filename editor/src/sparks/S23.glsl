// default: 1.30 1.02 0.92 22
// default-wide: 1.66 1.10 1.05 22
// S23 "Anschnitt" (lab_spark.c_anschnitt): riesiges Nest, Mitte ausserhalb der Seite, nur die Spitzen ragen herein.
vec4 spark_S23(vec2 p) {
  float R = uStar.z, rot = uStar.w;
  float d = starMain(p);
  int K = int(log(4.0 * uCell / R) / log(0.74)) + 1;            // Ringe bis ~4 Zellen, wie lab_spark.nest
  bool par = false;
  for (int k = 0; k < 64; k++) {
    if (k >= K) break;
    float fk = float(k);
    if (star(p, uStar.x, uStar.y, R * pow(0.74, fk), rot + 30.0 * fk) < 1.0) par = !par;
  }
  if (par) return vec4(0.5 + 0.5 * pow(clamp(1.0 - d, 0.0, 1.0), 0.7), 1.0, 0.0, 0.0);
  return vec4(bg(p) + 0.12 * exp(-max(d - 1.0, 0.0) / 0.25), 0.0, 0.0, 0.0);
}
