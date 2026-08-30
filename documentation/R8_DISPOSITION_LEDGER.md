# r8 catalog crosswalk and disposition ledger

Every record in the vendored r8 source (config/r8/) accounted for. Stable IDs on both sides; no record is silently out of scope. Regenerated deterministically by tools/generate_catalog_config.py.

- r8 part records: 152; keyboard records: 21.
- Dispositions: integrated_builder_catalog: 62, integrated_dome_catalog: 71, integrated_round2: 19, integrated_round2_keyboard_registry: 21, newer_measured_identity_unverified: 10, template_shell_abstraction: 2

## integrated_builder_catalog

- `conical_spring::deskeys` → `conical_springs::deskeys_conical` — Deskeys Conical Springs
- `conical_spring::dynacaps` → `conical_springs::dynacaps` — DynaCaps Conical Springs
- `conical_spring::klc_playground` → `conical_springs::klc_playground` — KLC Conical Springs
- `conical_spring::metapulse` → `conical_springs::metapulse` — MetaPulse Conical Springs
- `conical_spring::topre` → `conical_springs::topre` — Topre Conical Springs
- `housing::deskeys` → `housings::deskeys` — Deskeys Housings
- `housing::dynacaps` → `housings::dynacaps` — DynaCaps Housings
- `housing::klc_playground` → `housings::klc_playground` — KLC Housings
- `housing::metapulse` → `housings::metapulse` — MetaPulse Housings
- `housing::topre` → `housings::topre` — Topre Housings
- `silencing_ring::des_poron_0_2` → `silencing_ring::des_poron_0_2` — Deskeys 0.2 mm Poron Silencing Ring
- `silencing_ring::des_poron_0_3` → `silencing_ring::des_poron_0_3` — Deskeys 0.3 mm Poron Silencing Ring
- `silencing_ring::des_poron_0_4` → `silencing_ring::des_poron_0_4` — Deskeys 0.4 mm Poron Silencing Ring
- `silencing_ring::des_poron_0_5` → `silencing_ring::des_poron_0_5` — Deskeys 0.5 mm Poron Silencing Ring
- `silencing_ring::des_poron_0_6` → `silencing_ring::des_poron_0_6` — Deskeys 0.6 mm Poron Silencing Ring
- `silencing_ring::des_poron_0_7` → `silencing_ring::des_poron_0_7` — Deskeys 0.7 mm Poron Silencing Ring
- `silencing_ring::des_poron_1_0` → `silencing_ring::des_poron_1_0` — Deskeys 1.0 mm Poron Silencing Ring
- `silencing_ring::des_silicone_0_3` → `silencing_ring::des_silicone_0_3` — Deskeys 0.3 mm Silicone Silencing Ring
- `silencing_ring::des_silicone_0_5` → `silencing_ring::des_silicone_0_5` — Deskeys 0.5 mm Silicone Silencing Ring
- `silencing_ring::dynacaps_poron_0_3` → `silencing_ring::dynacaps_poron_0_3` — DynaCaps 0.3 mm Poron Silencing Ring
- `silencing_ring::dynacaps_poron_0_5` → `silencing_ring::dynacaps_poron_0_5` — DynaCaps 0.5 mm Poron Silencing Ring
- `silencing_ring::dynacaps_silicone_0_3` → `silencing_ring::dynacaps_silicone_0_3` — DynaCaps 0.3 mm Silicone Silencing Ring
- `silencing_ring::dynacaps_silicone_0_5` → `silencing_ring::dynacaps_silicone_0_5` — DynaCaps 0.5 mm Silicone Silencing Ring
- `silencing_ring::klc_poron_0_3` → `silencing_ring::klc_poron_0_3` — KLC 0.3 mm Poron Silencing Ring
- `silencing_ring::klc_silicone_0_3` → `silencing_ring::klc_silicone_0_3` — KLC 0.3 mm Silicone Silencing Ring
- `silencing_ring::metapulse_poron_0_5` → `silencing_ring::metapulse_poron_0_5` — MetaPulse 0.5 mm Poron Silencing Ring
- `silencing_ring::topre_poron_0_5` → `silencing_ring::topre_poron_0_5` — Topre 0.5 mm Poron Silencing Ring
- `silencing_ring::unreal_keyboards_poron_0_3` → `silencing_ring::unreal_keyboards_poron_0_3` — Unreal Keyboards 0.3 mm Poron Silencing Ring
- `silencing_ring::unreal_keyboards_poron_0_5` → `silencing_ring::unreal_keyboards_poron_0_5` — Unreal Keyboards 0.5 mm Poron Silencing Ring
- `silencing_ring::unreal_keyboards_poron_0_7` → `silencing_ring::unreal_keyboards_poron_0_7` — Unreal Keyboards 0.7 mm Poron Silencing Ring
- `silencing_ring::unreal_keyboards_poron_1_0` → `silencing_ring::unreal_keyboards_poron_1_0` — Unreal Keyboards 1.0 mm Poron Silencing Ring
- `silencing_ring::unreal_keyboards_silicone_0_3` → `silencing_ring::unreal_keyboards_silicone_0_3` — Unreal Keyboards 0.3 mm Silicone Silencing Ring
- `silencing_ring::unreal_keyboards_silicone_0_5` → `silencing_ring::unreal_keyboards_silicone_0_5` — Unreal Keyboards 0.5 mm Silicone Silencing Ring
- `slider::deskeys` → `slider::deskeys` — Deskeys Slider
- `slider::dynacaps` → `slider::dynacaps` — DynaCaps Slider
- `slider::hhkb_type_s` → `slider::hhkb_type_s` — Topre Silent (Type-S) Slider
- `slider::klc_playground` → `slider::klc_playground` — KLC Slider
- `slider::metapulse` → `slider::metapulse` — MetaPulse Slider
- `slider::novatouch` → `slider::novatouch` — NovaTouch Slider
- `slider::topre` → `slider::topre` — Topre Slider
- `slider::topre_silenced_purple` → `slider::topre_silenced_purple` — Topre Silent (Realforce) Slider
- `spacebar_stabilizer::deskeys` → `spacebar_stabilizer::deskeys` — Deskeys Spacebar Stabilizer
- `spacebar_stabilizer::dynacaps` → `spacebar_stabilizer::dynacaps` — DynaCaps Spacebar Stabilizer
- `spacebar_stabilizer::klc_playground` → `spacebar_stabilizer::klc_playground` — KLC Spacebar Stabilizer
- `spacebar_stabilizer::metapulse` → `spacebar_stabilizer::metapulse` — MetaPulse Spacebar Stabilizer
- `spacebar_stabilizer::topre` → `spacebar_stabilizer::topre` — Topre Spacebar Stabilizer
- `stabilizer_housing::deskeys` → `stabilizer_housing_2u::deskeys` — Deskeys Stabilizer Housing
- `stabilizer_housing::dynacaps` → `stabilizer_housing_2u::dynacaps` — DynaCaps Stabilizer Housing
- `stabilizer_housing::klc_playground` → `stabilizer_housing_2u::klc_playground` — KLC Stabilizer Housing
- `stabilizer_housing::metapulse` → `stabilizer_housing_2u::metapulse` — MetaPulse Stabilizer Housing
- `stabilizer_housing::novatouch` → `stabilizer_housing_2u::novatouch` — NovaTouch Stabilizer Housing
- `stabilizer_housing::topre_silenced` → `stabilizer_housing_2u::topre_silenced` — Topre Silent (Realforce) Stabilizer Housing
- `stabilizer_housing::topre_standard` → `stabilizer_housing_2u::topre_standard` — Topre Stabilizer Housing
- `stabilizer_slider::deskeys` → `stabilizer_slider_2u::deskeys` — Deskeys Stabilizer Slider
- `stabilizer_slider::dynacaps` → `stabilizer_slider_2u::dynacaps` — DynaCaps Stabilizer Slider
- `stabilizer_slider::hhkb_type_s` → `stabilizer_slider_2u::hhkb_type_s` — Topre Silent (Type-S) Stabilizer Slider
- `stabilizer_slider::klc_playground` → `stabilizer_slider_2u::klc_playground` — KLC Stabilizer Slider
- `stabilizer_slider::metapulse` → `stabilizer_slider_2u::metapulse` — MetaPulse Stabilizer Slider
- `stabilizer_slider::novatouch` → `stabilizer_slider_2u::novatouch` — NovaTouch Stabilizer Slider
- `stabilizer_slider::realforce_rc1_silenced_purple` → `stabilizer_slider_2u::realforce_rc1_silenced_purple` — Realforce RC1 Stabilizer Slider
- `stabilizer_slider::topre` → `stabilizer_slider_2u::topre` — Topre Stabilizer Slider
- `stabilizer_slider::topre_silenced` → `stabilizer_slider_2u::topre_silenced` — Topre Silent (Realforce) Stabilizer Slider

## integrated_dome_catalog

- `dome::astro_domes_120g` → `dm-astro-domes-120g` — Astro Domes 120g
- `dome::astro_domes_160g` → `dm-astro-domes-160g` — Astro Domes 160g
- `dome::astro_domes_35g` → `dm-astro-domes-35g` — Astro Domes 35g
- `dome::astro_domes_500g` → `dm-astro-domes-500g` — Astro Domes 500g
- `dome::astro_domes_50g` → `dm-astro-domes-50g` — Astro Domes 50g
- `dome::astro_domes_60g` → `dm-astro-domes-60g` — Astro Domes 60g
- `dome::astro_domes_70g` → `dm-astro-domes-70g` — Astro Domes 70g
- `dome::astro_domes_90g` → `dm-astro-domes-90g` — Astro Domes 90g
- `dome::bke_redux_v1_extreme` → `dm-bke-redux-v1-extreme` — BKE Redux v1 Extreme
- `dome::bke_redux_v1_heavy` → `dm-bke-redux-v1-heavy` — BKE Redux v1 Heavy
- `dome::bke_redux_v1_light` → `dm-bke-redux-v1-light` — BKE Redux v1 Light
- `dome::bke_redux_v1_ultra_light` → `dm-bke-redux-v1-ultra-light` — BKE Redux v1 Ultra Light
- `dome::des_carrots_35g` → `dm-des-carrots-35g` — Deskeys CARROTS 35g
- `dome::des_carrots_49g` → `dm-des-carrots-49g` — Deskeys CARROTS 49g
- `dome::des_carrots_60g` → `dm-des-carrots-60g` — Deskeys CARROTS 60g
- `dome::des_t1_100g` → `dm-des-t1-100g` — Deskeys T1 100g
- `dome::des_t1_28g` → `dm-des-t1-28g` — Deskeys T1 28g
- `dome::des_t1_35g` → `dm-des-t1-35g` — Deskeys T1 35g
- `dome::des_t1_42g` → `dm-des-t1-42g` — Deskeys T1 42g
- `dome::des_t1_49g` → `dm-des-t1-49g` — Deskeys T1 49g
- `dome::des_t1_56g` → `dm-des-t1-56g` — Deskeys T1 56g
- `dome::des_t1_63g` → `dm-des-t1-63g` — Deskeys T1 63g
- `dome::des_t1_70g` → `dm-des-t1-70g` — Deskeys T1 70g
- `dome::des_t1_85g` → `dm-des-t1-85g` — Deskeys T1 85g
- `dome::des_v1_35g` → `dm-des-v1-35g` — Deskeys V1 35g
- `dome::des_v1_42g` → `dm-des-v1-42g` — Deskeys V1 42g
- `dome::des_v1_49g` → `dm-des-v1-49g` — Deskeys V1 49g
- `dome::des_v1_56g` → `dm-des-v1-56g` — Deskeys V1 56g
- `dome::des_v2_35g` → `dm-des-v2-35g` — Deskeys V2 35g
- `dome::des_v2_42g` → `dm-des-v2-42g` — Deskeys V2 42g
- `dome::des_v2_49g` → `dm-des-v2-49g` — Deskeys V2 49g
- `dome::des_v2_56g` → `dm-des-v2-56g` — Deskeys V2 56g
- `dome::des_v2_63g` → `dm-des-v2-63g` — Deskeys V2 63g
- `dome::des_v2_70g` → `dm-des-v2-70g` — Deskeys V2 70g
- `dome::des_v3_28g` → `dm-des-v3-28g` — Deskeys V3 28g
- `dome::des_v3_35g` → `dm-des-v3-35g` — Deskeys V3 35g
- `dome::des_v3_42g` → `dm-des-v3-42g` — Deskeys V3 42g
- `dome::des_v3_49g` → `dm-des-v3-49g` — Deskeys V3 49g
- `dome::des_v3_56g` → `dm-des-v3-56g` — Deskeys V3 56g
- `dome::des_v3_63g` → `dm-des-v3-63g` — Deskeys V3 63g
- `dome::des_v3_70g` → `dm-des-v3-70g` — Deskeys V3 70g
- `dome::dynacaps_crazy_heavy` → `dm-dynacaps-crazy-heavy` — DynaCaps Crazy Heavy
- `dome::dynacaps_heavy` → `dm-dynacaps-heavy` — DynaCaps Heavy
- `dome::dynacaps_heavy_ish` → `dm-dynacaps-heavy-ish` — DynaCaps Heavy-ish
- `dome::dynacaps_light` → `dm-dynacaps-light` — DynaCaps Light
- `dome::dynacaps_medium` → `dm-dynacaps-medium` — DynaCaps Medium
- `dome::klc_playground_35g` → `dm-klc-playground-35g` — KLC 35g
- `dome::klc_playground_45g` → `dm-klc-playground-45g` — KLC 45g
- `dome::klc_playground_55g` → `dm-klc-playground-55g` — KLC 55g
- `dome::metapulse_bs_40g` → `dm-metapulse-bs-40g` — MetaPulse BS 40g
- `dome::metapulse_bs_50g` → `dm-metapulse-bs-50g` — MetaPulse BS 50g
- `dome::metapulse_bs_65g` → `dm-metapulse-bs-65g` — MetaPulse BS 65g
- `dome::metapulse_bs_75g` → `dm-metapulse-bs-75g` — MetaPulse BS 75g
- `dome::metapulse_rs_25g` → `dm-metapulse-rs-25g` — MetaPulse RS 25g
- `dome::metapulse_rs_30g` → `dm-metapulse-rs-30g` — MetaPulse RS 30g
- `dome::metapulse_rs_35g` → `dm-metapulse-rs-35g` — MetaPulse RS 35g
- `dome::metapulse_rs_40g` → `dm-metapulse-rs-40g` — MetaPulse RS 40g
- `dome::metapulse_rs_45g` → `dm-metapulse-rs-45g` — MetaPulse RS 45g
- `dome::metapulse_rs_55g_a` → `dm-metapulse-rs-55g-a` — MetaPulse RS 55g-A
- `dome::metapulse_rs_55g_b` → `dm-metapulse-rs-55g-b` — MetaPulse RS 55g-B
- `dome::niz_65g` → `dm-niz-65g` — NiZ 65g
- `dome::sony_bke_brown_01` → `dm-sony-bke-brown-01` — Sony BKE Brown 01
- `dome::sony_bke_brown_02` → `dm-sony-bke-brown-02` — Sony BKE Brown 02
- `dome::sony_bke_brown_03` → `dm-sony-bke-brown-03` — Sony BKE Brown 03
- `dome::sony_bke_gray_01` → `dm-sony-bke-gray-01` — Sony BKE Gray 01
- `dome::sony_bke_gray_02` → `dm-sony-bke-gray-02` — Sony BKE Gray 02
- `dome::topre_30g` → `dm-topre-30g` — Topre 30g
- `dome::topre_45g` → `dm-topre-45g` — Topre 45g
- `dome::topre_45g_aged` → `dm-topre-45g-aged` — Topre 45g Aged
- `dome::topre_55g` → `dm-topre-55g` — Topre 55g
- `dome::topre_55g_aged` → `dm-topre-55g-aged` — Topre 55g Aged

## integrated_round2

- `keycap::mx` → `keycap::mx` — MX Keycaps (added to the catalog in Round 2; previously omitted)
- `keycap::topre` → `keycap::topre` — Topre Keycaps (added to the catalog in Round 2; previously omitted)
- `keycap_oring::unreal_1_2` → `keycap_oring::unreal_1_2` — Keycap O-Rings (added to the catalog in Round 2; previously omitted)
- `landing_pad::des` → `landing_pad::des` — Deskeys Landing Pads (added to the catalog in Round 2; previously omitted)
- `landing_pad::unreal` → `landing_pad::unreal` — Unreal Keyboards Landing Pads (added to the catalog in Round 2; previously omitted)
- `pcb::generic` → `pcb::generic` — EC PCB (added to the catalog in Round 2; previously omitted)
- `plate::topre` → `plate::topre` — Topre Plate (added to the catalog in Round 2; previously omitted)
- `plate_gasket::des_poron_0_5` → `plate_gasket::des_poron_0_5` — Deskeys 0.5 mm Poron Plate Gasket (added to the catalog in Round 2; previously omitted)
- `plate_gasket::dynacaps_silicone_0_4` → `plate_gasket::dynacaps_silicone_0_4` — DynaCaps 0.4 mm Silicone Plate Gasket (added to the catalog in Round 2; previously omitted)
- `plate_gasket::unreal_poron_0_3` → `plate_gasket::unreal_poron_0_3` — Unreal Keyboards 0.3 mm Poron Plate Gasket (added to the catalog in Round 2; previously omitted)
- `plate_gasket::unreal_poron_0_3_hhkb` → `plate_gasket::unreal_poron_0_3_hhkb` — Unreal Keyboards 0.3 mm Poron Plate Gasket (HHKB) (added to the catalog in Round 2; previously omitted)
- `slider_gasket::des_0_5` → `slider_gasket::des_0_5` — Deskeys 0.5 mm Slider Gasket (added to the catalog in Round 2; previously omitted)
- `slider_gasket::des_0_7` → `slider_gasket::des_0_7` — Deskeys 0.7 mm Slider Gasket (added to the catalog in Round 2; previously omitted)
- `spacebar_spring::des` → `spacebar_spring::des` — Deskeys Housing Spring (added to the catalog in Round 2; previously omitted)
- `travel_spacer::des_poron_0_7` → `travel_spacer::des_poron_0_7` — Deskeys 0.7 mm Poron Dome Gasket (added to the catalog in Round 2; previously omitted)
- `travel_spacer::des_silicone_0_3` → `travel_spacer::des_silicone_0_3` — Deskeys 0.3 mm Silicone Dome Gasket (added to the catalog in Round 2; previously omitted)
- `travel_spacer::des_silicone_0_5` → `travel_spacer::des_silicone_0_5` — Deskeys 0.5 mm Silicone Dome Gasket (added to the catalog in Round 2; previously omitted)
- `travel_spacer::des_silicone_0_7` → `travel_spacer::des_silicone_0_7` — Deskeys 0.7 mm Silicone Dome Gasket (added to the catalog in Round 2; previously omitted)
- `travel_spacer::unreal_silicone_0_5` → `travel_spacer::unreal_silicone_0_5` — Unreal Keyboards 0.5 mm Silicone Travel Spacer (added to the catalog in Round 2; previously omitted)

## integrated_round2_keyboard_registry

- `kbd::agar_ec_kit` → `kbd::agar_ec_kit` — Agar EC Kit
- `kbd::ck980c` → `kbd::ck980c` — CK980C
- `kbd::hhkb` → `kbd::hhkb` — HHKB
- `kbd::hhkb_30th` → `kbd::hhkb_30th` — HHKB 30th Anniversary
- `kbd::hhkb_bt` → `kbd::hhkb_bt` — HHKB BT
- `kbd::hhkb_classic` → `kbd::hhkb_classic` — HHKB Classic
- `kbd::hhkb_classic_type_s` → `kbd::hhkb_classic_type_s` — HHKB Classic Type-S
- `kbd::hhkb_hybrid` → `kbd::hhkb_hybrid` — HHKB Hybrid
- `kbd::hhkb_hybrid_jp` → `kbd::hhkb_hybrid_jp` — HHKB Hybrid JP
- `kbd::hhkb_hybrid_type_s` → `kbd::hhkb_hybrid_type_s` — HHKB Hybrid Type-S
- `kbd::hhkb_pro_1` → `kbd::hhkb_pro_1` — HHKB Professional (Pro 1)
- `kbd::hhkb_pro_2` → `kbd::hhkb_pro_2` — HHKB Pro 2
- `kbd::hhkb_pro_2_jp` → `kbd::hhkb_pro_2_jp` — HHKB Pro 2 JP
- `kbd::hhkb_pro_2_jp_type_s` → `kbd::hhkb_pro_2_jp_type_s` — HHKB Pro 2 JP Type-S
- `kbd::hhkb_pro_2_type_s` → `kbd::hhkb_pro_2_type_s` — HHKB Pro 2 Type-S
- `kbd::hhkb_type_s` → `kbd::hhkb_type_s` — HHKB Type-S
- `kbd::leopold` → `kbd::leopold` — Leopold (family)
- `kbd::neverest` → `kbd::neverest` — NEVEREST
- `kbd::novatouch` → `kbd::novatouch` — Novatouch
- `kbd::realforce_r2` → `kbd::realforce_r2` — Realforce R2
- `kbd::realforce_rc1` → `kbd::realforce_rc1` — Realforce RC1

## newer_measured_identity_unverified

- `newer::dm-niz-purple-60g` → `dm-niz-purple-60g` — dm-niz-purple-60g (measured under fc-3.4; external catalog provenance not yet established)
- `newer::dm-topre-gx1-45g` → `dm-topre-gx1-45g` — dm-topre-gx1-45g (measured under fc-3.4; external catalog provenance not yet established)
- `newer::dm-topre-hhkb-pro2-45g` → `dm-topre-hhkb-pro2-45g` — dm-topre-hhkb-pro2-45g (measured under fc-3.4; external catalog provenance not yet established)
- `newer::dm-topre-r1-30g` → `dm-topre-r1-30g` — dm-topre-r1-30g (measured under fc-3.4; external catalog provenance not yet established)
- `newer::dm-topre-r1-45g` → `dm-topre-r1-45g` — dm-topre-r1-45g (measured under fc-3.4; external catalog provenance not yet established)
- `newer::dm-topre-r1-55g` → `dm-topre-r1-55g` — dm-topre-r1-55g (measured under fc-3.4; external catalog provenance not yet established)
- `newer::dm-topre-r2-30g` → `dm-topre-r2-30g` — dm-topre-r2-30g (measured under fc-3.4; external catalog provenance not yet established)
- `newer::dm-topre-r2-45g` → `dm-topre-r2-45g` — dm-topre-r2-45g (measured under fc-3.4; external catalog provenance not yet established)
- `newer::dm-topre-r2-55g` → `dm-topre-r2-55g` — dm-topre-r2-55g (measured under fc-3.4; external catalog provenance not yet established)
- `newer::dm-topre-rgb-45g` → `dm-topre-rgb-45g` — dm-topre-rgb-45g (measured under fc-3.4; external catalog provenance not yet established)

## template_shell_abstraction

- `shell::hhkb` → `shell::hhkb` — HHKB Shell (represents the r8 keyboard-scoped MetaPulse edges as shell pair edges; the shell is a Topre-molded housing array)
- `shell::rc1` → `shell::rc1` — Realforce RC1 Shell (represents the r8 keyboard-scoped MetaPulse edges as shell pair edges; the shell is a Topre-molded housing array)
