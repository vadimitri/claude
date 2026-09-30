// S7 "nest" (styles.spark): XOR-Nest aus 6 Sternen, je 0.74 kleiner und 30 Grad weiter gedreht.
vec4 spark_S7(vec2 p) {
  float d = starMain(p);
  bool m = false;
  for (int k = 0; k < 6; k++) {
    float fk = float(k);
    if (star(p, uStar.x, uStar.y, uStar.z * pow(0.74, fk), uStar.w + 30.0 * fk) < 1.0) m = !m;
  }
  if (!m) return vec4(-1.0, 0.0, 0.0, 0.0);
  return vec4(0.64 + 0.36 * pow(clamp(1.0 - d, 0.0, 1.0), 0.7), 1.0, 0.0, 0.0);
}
