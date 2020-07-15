This is a reaadme in Japanese

# PyHiLISPについて

PyHiSLIPは　High-Speed LAN Instrument Protocol (HiSLIP):

　http://www.ivifoundation.org/downloads/Class%20Specifications/IVI-6.1\_HiSLIP-1.1-2011-02-24.pdf

の Python による実装です。HiSLIP Clientを作成することができます。

PyHiSLIPは Levshinovskiy Mikhail氏によって開発されました。

 <https://github.com/llemish/PyHiSLIP.git>

英文のreadmeによると、original version は、Keysight N9030A and Keysight N5232A and Python
3.4+の組み合わせでテストされています。

ここに収められたバージョンは Noboru Yamamoto によって、

> 1.  Python2での動作
> 2.  SRQのサポート
> 3.  その他のコードのクリーンアップ(?)

などの変更が加えられました。ソースコードは、

　<https://github.com/noboruatkek/PyHiSLIP.git>

から入手可能です。このバージョンは、MacOSX 10.15 上のPython 2.7.17 /Python 3.8.2と "Kikusui
PWR401MH"の組み合わせでテストされました。

この装置ではWaveformの様な大きなデータを試すことはできませんでした。　(2020/5/7)

### Cython

pyhislip.pyx/pxdを用意することで、Cython化を行いました。
