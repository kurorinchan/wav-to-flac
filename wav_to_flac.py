#!/usr/bin/env python3
import argparse
import soundfile as sf
import os
import struct
import logging
import io
import wave

from mutagen.flac import FLAC

from dataclasses import dataclass


class Chunk:
    def __init__(self, chunk_id, data):
        self.chunk_id = chunk_id
        self.data = data


@dataclass
class TrackInfo:
    name: str = ''
    product: str = ''
    genre: str = ''
    year: str = ''


def _ReadChunkId(wav_file):
    byte = wav_file.read(1)
    if not byte:
        return None
    while byte == b'\x00':
        byte = wav_file.read(1)
        if not byte:
            return None

    return byte + wav_file.read(3)


def _ReadSize(wav_file):
    return struct.unpack('<I', wav_file.read(4))[0]


def _ParseChunks(wav_file):
    """Parses a chunk and returns all subchunks.

    Returns:
      Subchunks of the chunk.
    """
    chunk_id = _ReadChunkId(wav_file)
    chunk_size = _ReadSize(wav_file)
    chunk_format = wav_file.read(4)
    rest_of_chunk = wav_file.read(chunk_size - 4)
    logging.info('Found Chunk: {} {} {}'.format(chunk_id, chunk_size,
                                                chunk_format))

    subchunks = []
    buffer = io.BytesIO(rest_of_chunk)
    while True:
        subchunk = _OneSubChunk(buffer)
        if not subchunk:
            break
        subchunks.append(subchunk)

    return subchunks


def _OneSubChunk(wav_file):
    """Reads one subchunk and logs it.

    Returns:
      Returns a chunk if a chunk is found. None otherwise.
    """
    chunk_id = _ReadChunkId(wav_file)
    if not chunk_id:
        return None
    size = _ReadSize(wav_file)
    data = wav_file.read(size)
    logging.info('Subchunk: {} {}'.format(chunk_id, size))
    return Chunk(chunk_id, data)


def _ParseSubChunks(wav_file_path):
    sub_chunks = []
    with open(wav_file_path, 'rb') as wav_file:
        chunk_id = wav_file.read(4)
        # RIFF little endian, RIFX big endian: assume RIFF'
        if chunk_id != b'RIFF':
            return None

        _ = struct.unpack('<I', wav_file.read(4))[0]

        wav_format = wav_file.read(4)
        assert wav_format == b'WAVE', wav_format

        while True:
            sub_chunks.append(_OneSubChunk(wav_file))


_BytePerChannelMap = {
    1: 'PCM_S8',
    2: 'PCM_16',
    3: 'PCM_24',
}


def _ToFlac(wav_file):
    bytes_per_channel = _GetWavBytesPerChannel(wav_file)
    data, samplerate = sf.read(wav_file)
    file_path, _ = os.path.splitext(wav_file)
    flac_file_path = file_path + '.flac'

    sf.write(flac_file_path,
             data,
             samplerate,
             subtype=_BytePerChannelMap.get(bytes_per_channel, 'PCM_16'))

    logging.info('Transcoded {} to {}'.format(wav_file, flac_file_path))
    return flac_file_path


def _ParseTrackInfo(data):
    """Parses RIFF's LIST chunk's data and returns track info

    Returns:
      TrackInfo on success. None otherwise.
    """
    buffer = io.BytesIO(data)
    data_format = buffer.read(4)
    if data_format != b'INFO':
        logging.error(
            'Expected INFO format in LIST, but found {}'.format(data_format))
        return

    chunks = []
    while True:
        chunk = _OneSubChunk(buffer)
        if not chunk:
            break
        chunks.append(chunk)

    track_info = TrackInfo()

    for chunk in chunks:
        decoded = chunk.data.decode('shift-jis')
        if decoded[-1] == '\x00':
            decoded = decoded[:-1]
        if chunk.chunk_id == b'INAM':
            track_info.name = decoded
        elif chunk.chunk_id == b'ICRD':
            track_info.year = decoded
        elif chunk.chunk_id == b'IPRD':
            track_info.product = decoded
        elif chunk.chunk_id == b'IGNR':
            track_info.genre = decoded

    logging.info(track_info)
    return track_info


def _GetTrackInfo(subchunks):
    for subchunk in subchunks:
        if subchunk.chunk_id == b'LIST':
            return _ParseTrackInfo(subchunk.data)
    return None


def _GetWavTrackInfo(file_path):
    with open(file_path, 'rb') as wav_file:
        subchunks = _ParseChunks(wav_file)
        return _GetTrackInfo(subchunks)


def _GetWavBytesPerChannel(file_path):
    with wave.open(file_path, 'rb') as wav:
        return wav.getsampwidth()


def main():
    logging.basicConfig(level=logging.DEBUG)
    parser = argparse.ArgumentParser(
        description=
        'Converts wav files to flac files. '
        'The flac file is written next to the wav file. '
        'It assumes that the input wav file tags are written in SHIFT-JIS.'
    )
    parser.add_argument('files',
                        metavar='FILES',
                        type=str,
                        nargs='+',
                        help='Audio files to be converted to flac.')
    args = parser.parse_args()
    args.files
    for f in args.files:
        track_info = _GetWavTrackInfo(f)
        flac_file = _ToFlac(f)
        if not track_info:
            continue
        flac = FLAC(flac_file)
        flac["title"] = track_info.name
        flac["album"] = track_info.product
        flac["date"] = track_info.year
        logging.info(flac)
        flac.save()


if __name__ == "__main__":
    main()
