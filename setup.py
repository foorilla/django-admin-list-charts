from pathlib import Path

from setuptools import setup


about = {}
with open('admin_list_charts/__init__.py', encoding='utf-8') as f:
    exec(f.read(), about)

readme = Path('README.md').read_text(encoding='utf-8')


setup(
    name='django-admin-list-charts',
    version=about['__version__'],
    description='Super simple bar charts for django admin list views visualizing the number of objects based on date_hierarchy using Chart.js.',
    long_description=readme,
    long_description_content_type='text/markdown',
    url='https://github.com/foorilla/django-admin-list-charts',
    author=about['__author__'],
    author_email='pat@foorilla.com',
    license='MIT',
    packages=['admin_list_charts'],
    include_package_data=True,
    zip_safe=False,
    python_requires='>=3.12,<3.15',
    install_requires=['Django>=5,<7'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Framework :: Django :: 5.0',
        'Framework :: Django :: 5.1',
        'Framework :: Django :: 5.2',
        'Framework :: Django :: 6.0',
        'Intended Audience :: Developers',
        'Operating System :: OS Independent',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
        'Programming Language :: Python :: 3.14',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
