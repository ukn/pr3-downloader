set -e
export PR3_DEBUG=True
exe="./pr3-downloader.py"

echo "\n*** Test get_arts_from_pages - ./section/articles/"
$exe https://www.polskieradio.pl/9/53601

echo "\n*** Test get_arts_from_pages from page 5 - ./section/articles/"
$exe https://www.polskieradio.pl/9/5360 5

echo "\n*** Test get_arts_from_pages - ./ul/li/"
$exe https://www.polskieradio.pl/9/5403

echo "\n*** Test get_arts_from_tabs_content - ./section/articles/"
$exe https://www.polskieradio.pl/9/322

echo "\n*** Test get_arts_from_pages - ./section/articles/"
$exe https://www.polskieradio.pl/9/325
