from parser import RemParser



def main():
    # 2020 Data
    parser = RemParser("REM-2020.xls")
    parser.export_csv("output_2020.csv")
    parser.export_map("output_2020.html")
    #2019 Data
    parser = RemParser("REM-2019.xls")
    parser.export_csv("output_2019.csv")
    parser.export_map("output_2019.html")


if __name__ == "__main__":
    main()