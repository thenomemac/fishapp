FROM debian:8.5

MAINTAINER Josiah <thenomemac@gmail.com>

ENV LANG=C.UTF-8 LC_ALL=C.UTF-8

RUN apt-get update --fix-missing && apt-get install -y wget bzip2 ca-certificates \
    libglib2.0-0 libxext6 libsm6 libxrender1 \
    git mercurial subversion

RUN echo 'export PATH=/opt/conda/bin:$PATH' > /etc/profile.d/conda.sh && \
    wget --quiet https://repo.continuum.io/miniconda/Miniconda3-4.3.14-Linux-x86_64.sh -O ~/miniconda.sh && \
    /bin/bash ~/miniconda.sh -b -p /opt/conda && \
    rm ~/miniconda.sh

# RUN apt-get install -y curl grep sed dpkg && \
#     TINI_VERSION=`curl https://github.com/krallin/tini/releases/latest | grep -o "/v.*\"" | sed 's:^..\(.*\).$:\1:'` && \
#     curl -L "https://github.com/krallin/tini/releases/download/v${TINI_VERSION}/tini_${TINI_VERSION}.deb" > tini.deb && \
#     dpkg -i tini.deb && \
#     rm tini.deb && \
#     apt-get clean

ENV PATH /opt/conda/bin:$PATH

RUN conda install -y numpy pandas pillow h5py

RUN pip install gunicorn flask flask_bootstrap

# ENTRYPOINT [ "/usr/bin/tini", "--" ]
# CMD [ "/bin/bash" ]

# COPY logging.conf /logging.conf
# COPY gunicorn.conf /gunicorn.conf     

COPY fishapp fishapp

EXPOSE 8000

CMD ["gunicorn", "-b", ":8000", "--threads", "3", "fishapp:app"]
