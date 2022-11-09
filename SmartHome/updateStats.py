from logger import Log, LogException

def execute_4hour(mySQL):
    try:
        db, cursor = mySQL.getConnection()

        sql = "select value from measurements where kind='consumption' and source='powerwallDaily' order by time desc limit 2;"
        cursor.execute(sql)

        data = cursor.fetchall()

        if data:
            today = data[0][0]
            last_day = data[1][0]

            mySQL.insertCalculatedValue("production", "solar_today", today)
            mySQL.insertCalculatedValue("production", "solar_last_day", last_day)

    except Exception as e:
        Log("Error while writing to database for execute_4hour, exception:")
        LogException(e)
        return None

    return