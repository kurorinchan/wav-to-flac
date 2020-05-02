Tool for converting WAV file to FLAC. This assumes that the tags in WAV files
are written in SHIFT-JIS.

Some WAV file's tags assume certain kind of character encoding. This is because
WAV does not have a (standard) way of specifying it.
This script converts WAV to FLAC since FLAC has a standard way character
encoding scheme.
The conversion is done in a loss-less fashion, preserving bit-depth and sampling
rate.

# Setup
Install `pipenv`
```
pipenv install
```

## Run

```
pipenv run python ./wav_to_flac FILES
```