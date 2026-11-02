from pathlib import Path

from setuptools import find_namespace_packages
from setuptools import setup


about = {}
with open('admin_list_charts/__init__.py', encoding='utf-8') as f:
    exec(f.read(), about)

readme = Path('README.md').read_text(encoding='utf-8')
readme = readme.replace('(docs/gallery/', '(https://raw.githubusercontent.com/foorilla/django-admin-list-charts/main/docs/gallery/')
readme = readme.replace('(docs/', '(https://github.com/foorilla/django-admin-list-charts/blob/main/docs/')


setup(
    name='django-admin-list-charts',
    version=about['__version__'],
    description='Automatic, accessible charts for Django admin changelists.',
    long_description=readme,
    long_description_content_type='text/markdown',
    url='https://github.com/foorilla/django-admin-list-charts',
    author=about['__author__'],
    author_email='pat@foorilla.com',
    license='MIT',
    packages=find_namespace_packages(include=['admin_list_charts', 'admin_list_charts.*']),
    include_package_data=True,
    zip_safe=False,
    python_requires='>=3.12,<3.16',
    install_requires=[
        'Django>=5.2,<6.2; python_version < "3.15"',
        'Django>=6.1.3,<6.2; python_version >= "3.15"',
    ],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Framework :: Django :: 5.2',
        'Framework :: Django :: 6.0',
        'Framework :: Django :: 6.1',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Programming Language :: Python :: 3.14',
        'Programming Language :: Python :: 3.15',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
