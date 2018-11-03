FROM sd2e/reactors:python3-edge

COPY s3helpers.py /s3helpers.py
COPY agavehelpers.py /agavehelpers.py
COPY posixhelpers.py /posixhelpers.py
COPY copyfile.py /copyfile.py
COPY routemsg.py /routemsg.py

RUN pip uninstall --yes datacatalog
# COPY datacatalog /datacatalog

RUN pip3 install --upgrade git+https://github.com/SD2E/python-datacatalog.git@develop

