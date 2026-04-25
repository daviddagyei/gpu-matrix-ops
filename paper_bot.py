from alpaca_engine import run_spy_sma_paper_bot_df


def main() -> None:
    df = run_spy_sma_paper_bot_df(symbol="SPY", qty=1, max_position_qty=1, submit_orders=True)
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
