# syntax=docker/dockerfile:1
# Build context is addon/urmet-gateway/, nothing outside it.
# Stage 1 compiles the pjsua2 (PJSIP 2.17) wheel from a sha256-pinned tarball
# with the vendored wildcard-cert patch and the required config_site.h switches.
# Recipe mirrors vendor/urmet-sdk/docs/pjsua2-install.md.
FROM ghcr.io/home-assistant/base-debian:trixie AS builder

ARG PJPROJECT_VERSION=2.17
# Reproducible from github.com and codeload.github.com; verified twice.
ARG PJPROJECT_SHA256=065fe06c06788d97c35f563796d59f00ce52fe9558a52d7b490a042a966facce
ENV DEBIAN_FRONTEND=noninteractive

# Toolchain plus the -dev libraries autoconf detects: TLS (openssl), video
# (ffmpeg + openh264 + x264), audio (alsa + opus). SRTP uses pjproject's bundled
# copy, so no libsrtp2-dev. libavdevice-dev is deliberately absent (see below).
# libsdl2-dev gives pjmedia a video render device: pjsua cannot bring up an
# incoming video decode channel without one (it fails PJMEDIA_EVID_INVDEV and no
# decoded stream reaches the tap), so headless still needs a renderer. It is
# driven off-screen at runtime through SDL's dummy video driver, never a display.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential swig pkg-config uuid-dev ca-certificates curl \
        python3 python3-dev python3-pip python3-setuptools python3-wheel \
        libssl-dev libopus-dev libasound2-dev libsdl2-dev \
        libavcodec-dev libavformat-dev libavutil-dev libswscale-dev libswresample-dev \
        libopenh264-dev libx264-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build
# The wildcard-cert patch travels with the SDK version it was written for.
COPY vendor/urmet-sdk/patches/pjsip-2.17-accept-wildcard-cert.patch /build/pjsip.patch

# Fetch, verify against the pin, unpack. A wrong hash aborts here, never later.
RUN curl -fsSL -o pjproject.tar.gz \
        "https://github.com/pjsip/pjproject/archive/refs/tags/${PJPROJECT_VERSION}.tar.gz" \
    && echo "${PJPROJECT_SHA256}  pjproject.tar.gz" | sha256sum -c - \
    && tar xzf pjproject.tar.gz \
    && rm pjproject.tar.gz

WORKDIR /build/pjproject-2.17
# RFC 6125 wildcard acceptance for sip.urmet.com's *.urmet.com certificate.
RUN patch -p1 < /build/pjsip.patch

# Only the switches configure never raises on Linux. PJMEDIA_HAS_FFMPEG is left
# out on purpose: it would force PJMEDIA_HAS_LIBAVDEVICE, which we do not ship.
RUN printf '%s\n' \
    '#ifndef __PJ_CONFIG_SITE_H__' \
    '#define __PJ_CONFIG_SITE_H__' \
    '#define PJMEDIA_HAS_VIDEO               1' \
    '#define PJMEDIA_HAS_SRTP                1' \
    '#define PJSIP_HAS_TLS_TRANSPORT         1' \
    '#define PJMEDIA_AUDIO_DEV_HAS_ALSA      1' \
    '#define PJMEDIA_AUDIO_DEV_HAS_PORTAUDIO 0' \
    '#define PJSIP_MAX_PKT_LEN               8000' \
    '#define PJ_LOG_MAX_LEVEL               5' \
    '#define PJMEDIA_STREAM_ENABLE_KA        1' \
    '#endif' \
    > pjlib/include/pj/config_site.h

# make dep is skipped on purpose: it writes corrupt .depend files (upstream bug)
# and this is a clean tree, so nothing needs the dependency graph.
RUN ./configure CFLAGS="-fPIC -O2" CXXFLAGS="-fPIC -O2" LDFLAGS="-fPIC" \
        --prefix=/build/prefix \
    && make -j"$(nproc)" \
    && make install

# make wheel runs setup.py bdist_wheel. Never `make install` here: it runs
# setup.py install --user, dropping the module outside the environment, exit 0.
WORKDIR /build/pjproject-2.17/pjsip-apps/src/swig/python
RUN make wheel PYTHON_EXE=/usr/bin/python3 \
    && mkdir -p /wheels \
    && cp dist/*.whl /wheels/

# Stage 2: slim runtime. No compiler, no headers, no build tree.
FROM ghcr.io/home-assistant/base-debian:trixie

LABEL io.hass.type="addon" io.hass.arch="amd64" io.hass.version="0.1.0"

# The S6 grace times give the SIGTERM SIP-release path room before SIGKILL,
# while staying under the container stop timeout.
ENV DEBIAN_FRONTEND=noninteractive \
    S6_KILL_GRACETIME=9000 \
    S6_SERVICES_GRACETIME=9000 \
    SDL_VIDEODRIVER=dummy

# ffmpeg (the re-encode process) also pulls the libav*/libsw*, libasound, libopus
# and libssl that pjsua2 links; libavcodec-extra adds x264; libopenh264-8 is the
# OpenH264 2.5.x soname Debian trixie ships and the stage-1 wheel links against.
# libsdl2-2.0-0 is the runtime for pjmedia's video renderer; SDL_VIDEODRIVER=dummy
# above drives it off-screen so the decode channel comes up with no display.
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg libavcodec-extra libopenh264-8 libsdl2-2.0-0 \
        python3 python3-pip ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# pjsua2 wheel first, then the vendored SDK and the gateway. Both private packages
# come from the context; aiohttp/aiortc/av/pydantic are PyPI wheels.
COPY --from=builder /wheels /wheels
RUN pip3 install --no-cache-dir --break-system-packages /wheels/*.whl

WORKDIR /app
COPY vendor/urmet-sdk /app/vendor/urmet-sdk
COPY pyproject.toml /app/pyproject.toml
COPY urmet_gateway /app/urmet_gateway
RUN pip3 install --no-cache-dir --break-system-packages ./vendor/urmet-sdk \
    && pip3 install --no-cache-dir --break-system-packages .

# Acceptance criterion for the image: the native binding loads and ffmpeg runs.
RUN python3 -c "import pjsua2; ep = pjsua2.Endpoint(); ep.libCreate(); print('pjsua2', ep.libVersion().full)" \
    && ffmpeg -version > /dev/null

# The s6-overlay v3 service tree (init-urmet oneshot, urmet-gateway longrun).
COPY rootfs /
