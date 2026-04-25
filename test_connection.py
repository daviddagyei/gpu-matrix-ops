from alpaca_engine import get_connection_status_df


def main() -> None:
    df = get_connection_status_df()
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
