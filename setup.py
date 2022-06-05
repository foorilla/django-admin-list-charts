from setuptools import setup

import admin_list_charts


setup(
    name='django-admin-list-charts',
    version=admin_list_charts.__version__,
    description='Super simple bar charts for django admin list views visualizing the number of objects based on date_hierarchy using Chart.js.',
    url='https://github.com/foorilla/django-admin-list-charts',
    author=admin_list_charts.__author__,
    author_email='pat@foorilla.com',
    license='BSD 2-clause',
    packages=['admin_list_charts'],
    include_package_data=True,
    zip_safe=False,
    python_requires='>=3.6',
    install_requires=['Django>=3.2'],
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Web Environment',
        'Framework :: Django',
        'Framework :: Django :: 3.2',
        'Framework :: Django :: 4.0',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
        'Natural Language :: English',
        'Programming Language :: Python',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
)
