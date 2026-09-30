// S2 "grad" (styles.spark): geditherter Glutverlauf zur Mitte, nur im Stern deckend.
vec4 spark_S2(vec2 p) {
  float d = starMain(p);
  if (d >= 1.0) return vec4(-1.0, 0.0, 0.0, 0.0);
  return vec4(0.64 + 0.36 * pow(clamp(1.0 - d, 0.0, 1.0), 0.7), 1.0, 0.0, 0.0);
}
