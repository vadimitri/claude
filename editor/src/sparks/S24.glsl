// default: 0.5A 0.5B 0.98 30
// default-wide: 0.5A 0.5B 1.18 0
// S24 "Rahmen" (lab_spark.c_rahmen): Seite liegt im Stern, die Ecken sind das Aussen, Ringe reissen den Rand auf.
vec4 spark_S24(vec2 p) {
  float d = starMain(p);
  float v;
  if (d < 1.0) v = d > 0.975 ? 0.9 : bg(p, 0.04, 0.10) + 0.12 * pow(clamp(d, 0.0, 1.0), 4.0);
  else v = fract(d * 9.0) < 0.5 ? 0.38 + 0.4 * exp(-(d - 1.0) / 0.15) : 0.0;
  return vec4(v, v >= 0.5 ? 1.0 : 0.0, 0.0, 0.0);
}
