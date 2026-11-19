-- Seed de desarrollo local. Tarifas de créditos de ejemplo (PROVISIONALES:
-- los valores definitivos son una decisión de negocio pendiente).
insert into public.credit_rates (provider, operation, unit, credits_per_unit) values
  ('anthropic', 'llm_call',        'request', 1),
  ('kokoro',    'tts',             'second',  0.1),
  ('remotion',  'render_template', 'second',  0.5)
on conflict do nothing;
