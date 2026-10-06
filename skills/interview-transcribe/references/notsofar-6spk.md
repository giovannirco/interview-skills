# NOTSOFAR-1 eval, 6 speakers (2026-09-25) — why Nemotron is not the default for 2–3 person calls but wins on big rooms

Held-out set: `microsoft/NOTSOFAR` `240629.1_eval_small_with_GT`. Nemotron's card trains on NOTSOFAR train and dev, not this eval split. AMI and VoxConverse were skipped because those splits are in that training table.

Selection, fixed before inference: of 80 eval-small meetings, 7 have exactly 6 participants. Sorted by meeting id. Scored the first and the last. No listening.

| Meeting | Device | Tag | Duration |
|---------|--------|-----|----------|
| MTG_32178 | sc_meetup_0 | FarLowTalker | 358s |
| MTG_32191 | sc_rockfall_0 | StandSit | 360s |

Reference is the released word timings. DER uses collar 0 and scores overlap. That is not NVIDIA's forced-alignment RTTM, so these numbers are not a reproduction of the model-card full-set DER.

| System | MTG_32178 DER | words | speakers | MTG_32191 DER | words | speakers |
|--------|-------------:|------:|---------:|-------------:|------:|---------:|
| Nemotron 3 offline | 12.5% | 94.0% | 6 | 16.7% | 92.1% | 7 |
| community-1 regular, num_speakers=6 | 25.1% | 83.5% | 6 | 23.7% | 85.2% | 6 |
| community-1 regular, auto count | 24.6% | 82.6% | 5 | 23.7% | 85.2% | 6 |
| community-1 exclusive, num_speakers=6 | 29.7% | 76.5% | 6 | 31.2% | 75.7% | 6 |
| segment ECAPA spectral, num_speakers=6 | 32.4% | 78.2% | 6 | 36.0% | 74.6% | 6 |

mlx-whisper large-v3-turbo, speaker-agnostic, against the close-talk reference: normalized WER 85.7% and 87.8%. The far microphone and the reference diverge from the first sentence. That WER does not rank the diarizers.

Audio was downloaded from the public NOTSOFAR dataset; nothing here is from a real interview.
