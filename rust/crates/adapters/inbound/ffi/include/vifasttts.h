#ifndef VIFASTTTS_H
#define VIFASTTTS_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef struct VifasttOptions {
  float speed;
  float alpha;
  size_t max_chars;
  uint8_t fixed_pauses;
  uint8_t peak_normalize;
} VifasttOptions;

typedef void *VifasttEngine;
typedef int (*VifasttChunkCallback)(const float *samples, size_t len,
                                    uint32_t sample_rate, void *user_data);

const char *vifasttts_last_error(void);
const char *vifasttts_version(void);
const char *vifasttts_ort_info(void);

VifasttEngine vifasttts_engine_new(const char *acoustic, const char *vocoder);
VifasttEngine vifasttts_engine_new_vfts(const char *vfts);
VifasttEngine vifasttts_engine_new_vfa(const char *vfa, const char *vocoder);
VifasttEngine vifasttts_engine_new_vfa_auto(const char *vfa);
VifasttEngine vifasttts_engine_new_verified(const char *acoustic,
                                            const char *vocoder,
                                            const char *manifest);
VifasttEngine vifasttts_engine_from_bytes(const uint8_t *acoustic,
                                          size_t acoustic_len,
                                          const uint8_t *vocoder,
                                          size_t vocoder_len);
void vifasttts_engine_free(VifasttEngine engine);

uint8_t *vifasttts_synthesize(VifasttEngine engine, const char *text,
                              const VifasttOptions *options, size_t *out_len);
int vifasttts_synthesize_karaoke(VifasttEngine engine, const char *text,
                                 const VifasttOptions *options,
                                 uint8_t **out_wav, size_t *out_wav_len,
                                 char **out_karaoke_json);
int vifasttts_synthesize_stream(VifasttEngine engine, const char *text,
                                const VifasttOptions *options,
                                VifasttChunkCallback callback,
                                void *user_data);
void vifasttts_buffer_free(uint8_t *ptr, size_t len);
void vifasttts_string_free(char *value);

#ifdef __cplusplus
}
#endif
#endif
