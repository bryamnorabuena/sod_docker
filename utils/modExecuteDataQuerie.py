import pymysql

def connect_db(settings, queryInstruction, queryBlocks, params):
    conn = pymysql.connect(
        host=settings['host'],
        port=settings['port'],
        user=settings['user'],
        password=settings['password'],
        database=settings['database'],
        cursorclass=pymysql.cursors.DictCursor
    )
    
    try:
        with conn.cursor() as cursor:
            for block in queryBlocks:
                if params is None:
                    cursor.execute(';'.join(block))
                else:
                    cursor.execute(';'.join(block), params)
            
            # Para procedimientos almacenados
            if 'sp' in queryInstruction:
                conn.commit()
                results = cursor.fetchall()
                return [results, None, None]
            
            # Para operaciones que modifican datos
            if queryInstruction in ['insert', 'update', 'delete', 'insertBatchProcess']:
                conn.commit()
                if queryInstruction == 'insertBatchProcess':
                    batch = cursor.fetchone()[0] if cursor.rowcount > 0 else None
                    return [None, None, batch]
                return [cursor.fetchall(), None, None]
            
            results = cursor.fetchall()
            return [results, None, None]
            
    finally:
        conn.close()

def create_query_dict(dbSettings, queryInstruction, queryBlocks, params=None):
    queryData, _, _ = connect_db(dbSettings, queryInstruction, queryBlocks, params)
    
    if queryData is None:
        return []
    return list(queryData)