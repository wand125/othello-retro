# Short interface

9:16の盤面で、入力・復元計算・巻き戻し・合法棋譜の再生を行うUIです。効果音はWeb Audioで合成し、未設定時の音色は「木の石」です。保存済みの音色設定（例：ポップ）と消音設定はブラウザ内で保持します。音声素材や動画ファイルは同梱していません。

以下のコマンドは、このリポジトリのルートから実行します。

```sh
python3 short/preview.py --port 18807
```

`http://127.0.0.1:18807/short` で静的プレビューを開けます。既定では外部の探索APIへ接続しません。自分で用意したAPIへ接続する場合は、そのoriginを明示します。

```sh
python3 short/preview.py --port 18807 --backend https://your-service.example
# ローカルで動かすAPIの場合
python3 short/preview.py --port 18807 --backend http://127.0.0.1:8080
```

APIは既存の `/api/solve`・`/api/result`・`/api/progress`・`/api/cancel` を実装する必要があります。元サービスの利用ログ・データベース・認証情報・Cloud設定は含みません。静的な棋譜例は `solver/ui/public-examples.json` から読みます。

Docker overlayを使う場合は、自分のベースイメージを指定します。`install_short.py` はコンテナ内の `/app/cloud/app.py` にShort用の静的ルートを加えるためのもので、ローカルの本番環境や環境変数を取得する処理はありません。既存の `/`・`/paper` と探索側のコードはベースイメージに由来します。

自作コードはMITです（[ライセンス範囲](../solver/WEB_LICENSES.md)、[MIT本文](../solver/licenses/MIT-web.txt)）。ShortはMediabunnyを使いません。元の動画制作UIで必要な依存関係は[第三者通知](../solver/THIRD_PARTY_WEB.md)を参照してください。

## English

This 9:16 interface edits a board, requests reconstruction, rewinds, and replays a legal record. Sounds are synthesized with Web Audio. Wood is the default tone only when there is no saved voice; explicit preferences such as pop and mute remain in browser storage. No audio recordings or user videos are bundled.

Run the commands above from the repository root. The preview binds to loopback and makes no reconstruction API requests unless `--backend` explicitly selects an API you control. HTTPS origins and local loopback HTTP origins are accepted. The original service's credentials, usage records, databases and deployment state are not included. Static records are read from `solver/ui/public-examples.json`.

The optional Docker overlay takes your own base image and adds Short assets/static routes. It does not extract environment configuration or copy an unrelated workspace application. The code is MIT; Short does not require Mediabunny.
