#!/usr/bin/bash

if [ -z "$extra_mailman_python_exact_version" ]; then
    echo "[MAILMAN PYTHON INSTALL]: no extra python specified for install for mailman. Not doing anything."
    exit 0
fi

python$extra_mailman_python_version --version > /dev/null 2>&1

if [ "x$?" = x0 ]; then
    echo "[MAILMAN PYTHON INSTALL]: extra python version $extra_mailman_python_version already present. Not doing anything."
    exit 0
fi

echo "[MAILMAN PYTHON INSTALL]: installing exact python version $extra_mailman_python_version for use with mailman..."

curl -L https://raw.githubusercontent.com/yyuu/pyenv-installer/master/bin/pyenv-installer | bash

touch /root/.bashrc
mv /root/.bashrc /root/.bashrc_tmp
echo 'export PATH="/root/.pyenv/bin:$PATH"' > /root/.bashrc_prepend_tmp
cat /root/.bashrc_prepend_tmp /root/.bashrc_tmp > /root/.bashrc

source '/root/.bashrc'
pyenv update
pyenv install $extra_mailman_python_exact_version

touch /root/.bashrc
mv /root/.bashrc /root/.bashrc_tmp
echo 'export PATH="/root/.pyenv/versions/'$extra_mailman_python_exact_version'/bin/:$PATH"' > /root/.bashrc_prepend_tmp
echo 'export PYTHON_EXTRA_PATH="/root/.pyenv/versions/'$extra_mailman_python_exact_version'/bin/"' >> /root/.bashrc_prepend_tmp
cat /root/.bashrc_prepend_tmp /root/.bashrc_tmp > /root/.bashrc

echo "[MAILMAN PYTHON INSTALL]: done installing python $extra_mailman_python_version!"

