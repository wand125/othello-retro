# WSL 公開サービス実測

ローカルCLIからHTTPSで8盤面を逐次送信。auto、各60秒、各1回。ブラウザを使用しません。
モデルはサービス内で保持され、各リクエストの開始状態は統制していません。処理時間と通信・待機を含む時間を分けて記録します。

| 盤面 | 結果 | 処理時間（秒） | 往復・待機込み（秒） |
|---|---|---:|---:|
| game-23ef861ba8ab | found | 0.009 | 0.630 |
| game-ab1283e52d76 | found | 1.172 | 1.832 |
| game-d85ca28d0454 | found | 11.108 | 11.643 |
| game-3e12889bd851 | found | 8.337 | 8.978 |
| game-0076b1cef372 | found | 9.288 | 9.782 |
| game-2c8b678b7c02 | found | 7.191 | 7.680 |
| game-ba2452f6e3fa | found | 18.868 | 19.474 |
| missing-center | unreachable | 0.003 | 0.741 |

{"reachable_runs": 7, "found_verified": 7, "unreachable_runs": 1, "unreachable_correct": 1, "unknown": 0, "invalid_or_wrong": 0, "successful_server_median_seconds": 8.337, "successful_wall_median_seconds": 8.978291, "failure_penalized_server_mean_seconds": 7.996142857142857}
