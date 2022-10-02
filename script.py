from calendar import c
from reprlib import recursive_repr
from string import Template
import requests
import pandas as pd
from pathlib import Path
from git import Repo
from git import rmtree
import os
import datetime
import threading


path = Path(__file__).parent

############################################INSIRA SEU TOKEN#####################################
headers = {"Authorization": "Bearer [INSIRA SEU TOKEN]"}


def run_query(query):

    request = requests.post('https://api.github.com/graphql',
                            json={'query': query}, headers=headers)
    if request.status_code == 200:
        return request.json()
    else:
        raise Exception("Query failed to run by returning code of {}. {}".format(
            request.status_code, query))


def updated_query(result):
    endCursor = result["data"]["search"]["pageInfo"]["endCursor"]
    print("endCursor", endCursor)
    odeioPY = '"'
    query = queryTemplate.substitute(after=odeioPY + endCursor + odeioPY)
    return query


def write_cvs(arq_name, data_df, contador, init):
    df = pd.DataFrame(data=data_df)
    df.to_csv(path / arq_name, sep=';',
              mode='a', header=(contador == init), index=False)


def delete_repo(path):
    print("deletando repositorio..")
    rmtree(path)


def delete_arq(arq):
    if os.path.exists(arq):
        os.remove(arq)


def clona_repo(url, dir):
    try:
        print('cloning ....', url)
        repo = Repo.clone_from(url, dir)
        print("clonado repo. ", url)
    except:
        clona_repo(url, dir)
    else:
        return repo


def find_ck(jarDir, dirRepo, outDir):
    # Chama CK
    run_ck = 'java -jar "' + str(jarDir) + '" "' + \
        str(dirRepo) + '" jars:true 0 False "' + str(outDir) + '"'
    os.system(run_ck)
    print(run_ck)


def metric_ck(outclass_dir, url, stars, idade, numRelease):
    try:
        if os.path.exists(outclass_dir):
            file_encoding = open(outclass_dir, encoding="utf-8",
                                 errors='backslashreplace')
            data = pd.read_csv(file_encoding, sep=',',
                               usecols=['cbo', 'dit', 'lcom', 'loc'], encoding="utf-8")

            df_metric = pd.DataFrame({
                'cbo': [data['cbo'].sum()],
                'dit': [data['dit'].sum()],
                'lcom': [data['lcom'].sum()],
                'loc': [data['loc'].sum()],
                'url': url,
                'stars': stars,
                'idade': idade,
                'numRelease': numRelease,
            })

            return df_metric
    # Notei que pode ocorrer erro na coleta do CK, no jar, ele pode escrever um arquivo vazio, caso não seja possivel realizar a metrica iremos ignorar a url e procegui o fluxo
    except:
        print("erro ao obter dados do arquivo ck")
        return None


def thread():
    return 0


# QUERY
queryTemplate = Template(
    """
query repo {
  search(query: "language:java", type: REPOSITORY, first: 10, after: $after){
    pageInfo {
      endCursor
      hasNextPage
    }
    nodes {
      ... on Repository {
        nameWithOwner
        createdAt
        updatedAt
        releases {
          totalCount
        }
        url
        stargazers {
          totalCount
        }
        primaryLanguage {
          name
        }
      }
    }
  }
}
"""
)


# MAIN
if __name__ == "__main__":
    try:
        init = 0

        contador = init
        endCursor = ""
        node_dic = []

        listRepo = "list-repositories.csv"
        listMetric = "metric-ck.csv"

        repo_dir = path / "repo"
        jar_dir = path / "ck.jar"
        result_dir = path / "out_ck" / "out"
        outclass_dir = path / 'out_ck'/'outclass.csv'

        query = queryTemplate.substitute(after="null")

        currentDateTime = datetime.datetime.now()
        anoAtual = currentDateTime.date().year

        while contador < 100:

            print("Chamada ", contador)
            # Chama o metodo de busca
            result = run_query(query)

            nodes = pd.json_normalize(result["data"]['search']['nodes'])

            # escreve no arquivo lista de repositorio
            write_cvs(listRepo, nodes, contador=contador, init=init)

            t = globals()

            columns_init = 0
            columns_count = nodes[nodes.columns[0]].count()

            while columns_init < columns_count:
                t[str(columns_init)] = threading.Thread(target=clona_repo, args=(
                    nodes.values[columns_init][3], repo_dir / str(columns_init)))

                t[str(columns_init)].start()

                columns_init += 1

            columns_init = 0
            while columns_init < columns_count:
                t[str(columns_init)].join()

                print("contador interno: ", columns_init)

                url = nodes.values[columns_init][3]
                idade = anoAtual - int(nodes.values[columns_init][1][0:4])
                stars = nodes.values[columns_init][5]
                releases = nodes.values[columns_init][4]

                find_ck(jar_dir, repo_dir / str(columns_init), result_dir)

                metric = metric_ck(outclass_dir=outclass_dir, url=url,
                                   numRelease=releases, idade=idade, stars=stars)

                # Escreve arq cvs a metrica
                write_cvs(listMetric, metric, contador=contador,
                          init=init-columns_init)

                # Deleta arquivo de metrica
                delete_arq(outclass_dir)
                delete_repo(path=repo_dir / str(columns_init))

                columns_init += 1

            # valida se possui nova pagina
            hasNextPage = result["data"]["search"]["pageInfo"]["hasNextPage"]

            if hasNextPage == True:
                # recupera endCursor e substitui a query
                query = updated_query(result)
                contador += 1
            else:
                contador = 100

    except Exception as e:
        print("An exception occurred", e)
