import itertools
import json
import logging
import tempfile
import os
from pathlib import Path
from urllib.parse import urlencode, urljoin
from uuid import uuid4

import pydash
from doit import create_after

import audiosegment as AudioSegment

from thinkdsp import read_wave
from thinkdsp import WavFileWriter

DOIT_CONFIG = {"action_string_formatting": "new"}

  
# -----------------------------------------------------------------------------

_DIR = Path(__file__).parent

# Temporary directory
_tempdir_obj = tempfile.TemporaryDirectory()
_TEMPDIR = Path(_tempdir_obj.name)

logging.basicConfig(level=logging.DEBUG)
_LOGGER = logging.getLogger("dodo")

_CONFIG_PATH = _DIR / "config.json"
_LOGGER.debug("Loading config from %s", _CONFIG_PATH)
with open(_CONFIG_PATH, "r") as config_file:
    _CONFIG = json.load(config_file)

_CACHE_DIR = _DIR / "cache"
_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def task_impulse_responses():
    # Gets sounds to convolve
    ir_dir = _DIR / pydash.get(_CONFIG, "impulse-response.ir_directory")
    ir_dir.mkdir(parents=True, exist_ok=True)
    
    files = pydash.get(_CONFIG, "impulse-response.files")
    base_url = pydash.get(_CONFIG, "impulse-response.base_url")
    for file_name in files:
        file_path = ir_dir / file_name
        if not file_path.exists():
            # Download
            file_url = urljoin(base_url, file_name)
            yield {
                "name": f"download_{file_name}",
                "targets": [file_path],
                "actions": [f"wget -O {{targets}} '{file_url}'"],
            }
        # Extract
        yield {
            "name": f"extract_{file_name}",
            "file_dep": [file_path],
            "actions": [f"tar -C '{ir_dir}' -xf {{dependencies}}"],
        }

def task_phrase():
    # Gets phrases to convolve
    phrase_dir = _DIR / pydash.get(_CONFIG, "phrase.phrase_directory")
    phrase_dir.mkdir(parents=True, exist_ok=True)
    
    files = pydash.get(_CONFIG, "phrase.files")
    base_url = pydash.get(_CONFIG, "phrase.base_url")
    for file_name in files:
        file_path = phrase_dir / file_name
        if not file_path.exists():
            # Download
            file_url = urljoin(base_url, file_name)
            yield{
                "name": f"download_{file_name}",
                "targets": [file_path],
                "actions": [f"wget -O {{targets}} '{file_url}'"]
            }
        # Extract
        yield {
            "name": f"extract_{file_name}",
            "file_dep": [file_path],
            "actions": [f"tar -C '{phrase_dir}' -xf {{dependencies}}"],
        }

def reset_framerate(dsp_wav, new_fr):

  try:
    temp_wav = tempfile.TemporaryFile()
    temp_wav_path_name = "/".join([tempfile.tempdir, str(temp_wav.name)])
    dsp_wav.write(temp_wav_path_name)
    as_wav1 = AudioSegment.from_file(temp_wav_path_name)
    as_wav1 = as_wav1.set_frame_rate(new_fr)
    as_wav1.export(temp_wav_path_name, format="wav")
    dsp_wav = read_wave(temp_wav_path_name)
  finally:
    temp_wav.close()

  return dsp_wav


def convolve_wavs(p_file, c_file, cvd_file_path):
    print (p_file)
    print (c_file)
    dsp_wav1 = read_wave(str(p_file))
    dsp_wav2 = read_wave(str(c_file))
    if dsp_wav1.framerate > dsp_wav2.framerate:
      dsp_wav1 = reset_framerate(dsp_wav1, dsp_wav2.framerate)
    elif dsp_wav2.framerate > dsp_wav1.framerate:
      dsp_wav2 = reset_framerate(dsp_wav2, dsp_wav1.framerate)

    dsp_conv = dsp_wav2.convolve(dsp_wav1)
    dsp_conv.write(str(cvd_file_path))
 

@create_after(executed="impulse_responses")
@create_after(executed="phrase")
def task_convolve_phrases_directories():
    # Convolve phrases and sounds
    convolved_dir = _DIR / pydash.get(_CONFIG, "convolved.convolved_directory")
    convolved_dir.mkdir(parents=True, exist_ok=True)
        
    ir_dir = _DIR / pydash.get(_CONFIG, "impulse-response.ir_directory")
    phrase_dir = _DIR / pydash.get(_CONFIG, "phrase.phrase_directory")

    convolved_dir = _DIR / pydash.get(_CONFIG, "convolved.convolved_directory")
    convolved_dir.mkdir(parents=True, exist_ok=True)
    
    p_tar_files = pydash.get(_CONFIG, "phrase.files")
    i_tar_files = pydash.get(_CONFIG, "impulse-response.files")
    for p_tar_file in p_tar_files:
      p_tar_file_dir = p_tar_file.split(".")[0]
      phrase_dir_p = Path(phrase_dir) / p_tar_file_dir
      for i_tar_file in i_tar_files:
        i_tar_file_dir = i_tar_file.split(".")[0]      
        ir_dir_p = Path(ir_dir) / i_tar_file_dir
        for p_file in phrase_dir_p.iterdir():
          if p_file.suffix == ".wav":
            for c_file in ir_dir_p.iterdir():
              if c_file.suffix == ".wav":
                p_name_only = p_file.name[:-len(p_file.suffix)]
                cvd_file_name =  p_name_only + "_" + c_file.name
                cvd_file_path = convolved_dir / cvd_file_name
                if not cvd_file_path.exists():
                  yield {
                      'name': cvd_file_path,
                      'actions': [(convolve_wavs, [], {
                          'p_file': p_file,
                          'c_file': c_file,
                          'cvd_file_path': cvd_file_path})],
                          'targets': [cvd_file_path],
                  }