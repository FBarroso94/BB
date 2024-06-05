import logging
import sys
import time
import traceback
from types import NoneType
from selenium import webdriver
from selenium.common import NoSuchElementException, StaleElementReferenceException, TimeoutException
from selenium.webdriver import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions
from selenium.webdriver.support.wait import WebDriverWait
import keyring
import pandas as pd
from datetime import datetime
import os
import json
import gspread
from google.oauth2.service_account import Credentials

now = datetime.now()
pd.reset_option('max_columns')
pd.set_option('display.max_columns', 10)
log_filename = 'session_log_' + now.strftime("%Y%m%d%H%M%S") + '.csv'

# Edge driver
# from selenium.webdriver.edge.service import Service
# service_obj = Service("/Users/YN557KV/AppData/Local/Programs/MSEdge Webdriver/msedgedriver")
# driver = webdriver.Edge(service=service_obj)
#

# Credentials
servicename = "Login"
username = "31992.155136"
agencia = username.split(".")[0]
conta = username.split(".")[1]

if keyring.get_password(servicename, username):
    password = keyring.get_password(servicename, username)

# Constants

TODAY = datetime.strftime(datetime.today(), "%d/%m/%Y")
SEARCH_STRING = "cartões - fatura - extrato"

# Chrome driver
service_obj = Service("C:/_Dev/chrome-webdriver/chromedriver.exe")
driver = webdriver.Chrome(service=service_obj)
# 5 seconds is max timeout
driver.implicitly_wait(7)
# explicit 10s wait
wait_10s = WebDriverWait(driver, 10)
driver.delete_all_cookies()


# Functions
def sendKeysTo(xpath, text):
    driver.find_element(By.XPATH, xpath).send_keys(text)


def navigateToByClick(xpath):
    driver.find_element(By.XPATH, xpath).click()


def readElement(xpath):
    data = driver.find_element(By.XPATH, xpath).get_attribute("innerHTML")
    return data


def readXpaths(filepath):
    # Opening JSON file
    f = open(filepath)

    # returns JSON object as 
    # a dictionary
    data = json.load(f)

    # Closing file
    f.close()

    return data[0]


def loginBB():
    print("Opening Banco do Brasil...")
    driver.get("https://www.bb.com.br/site/")
    driver.maximize_window()
    print("Opened!")
    navigateToByClick("//*[@id='header']/header/bb-navbar-header/nav/div[2]/div[2]/bb-navbar-dropdown/button")
    # driver.find_element(By.XPATH, "//*[@id='header']/header/bb-navbar-header/nav/div[2]/div[2]/bb-navbar-dropdown/button").click()

    navigateToByClick("//*[@id='cdk-overlay-0']/bb-dropdown-menu/bb-menu/ul/li[1]/a")
    # driver.find_element(By.XPATH, "//*[@id='cdk-overlay-0']/bb-dropdown-menu/bb-menu/ul/li[1]/a").click()

    sendKeysTo("//*[@id='dependenciaOrigem']", agencia)
    # driver.find_element(By.XPATH, "//*[@id='dependenciaOrigem']").send_keys(agencia)
    sendKeysTo("//*[@id='numeroContratoOrigem']", conta)
    # driver.find_element(By.XPATH, "//*[@id='numeroContratoOrigem']").send_keys(conta)

    navigateToByClick("//*[@id='botaoEnviar']")
    # driver.find_element(By.XPATH, "//*[@id='botaoEnviar']").click()

    sendKeysTo("//*[@id='senhaConta']", password)
    # driver.find_element(By.XPATH, "//*[@id='senhaConta']").send_keys(password)

    navigateToByClick("//*[@id='botaoEnviar']")
    # driver.find_element(By.XPATH, "//*[@id='botaoEnviar']").click()
    print("Username and password sent. Logging in...")
    # driver.find_element(By.CLASS_NAME, "app-header__logo-container")
    print("Logged!")


def accessMultiStatement(paths):
    # wait_10s.until(expected_conditions.presence_of_element_located((By.XPATH,xpaths['Minhas financas'])))
    time.sleep(5)
    navigateToByClick(paths['Minhas financas'])

    navigateToByClick(paths['Extrato Multibanco'])
    navigateToByClick(paths['Checkbox Caixa'])
    obj = driver.find_element(By.XPATH, paths['Titulo Extrato Multibanco'])
    if obj:
        return True
    else:
        return False


def readTransactions(paths):
    df = pd.DataFrame(
        columns=["ID", "DescricaoBanco", "ComplementoDescricao", "Valor", "DataCompra", "DataLancamento", "Banco",
                 "TipoLancamento", "Parcela", "Parcelas", "Categoria", "Subcategoria"])
    day = 1
    transaction = 1
    while True:
        try:
            diaMes = readElement(paths['Div dia'].replace('{n}', str(day)))
        except:
            # Fim da Pagina
            transaction = 1
            day = 1
            break

        try:
            descXpath = paths['Descricao lancamento']
            descXpath = descXpath.replace('{d}', str(day))
            descXpath = descXpath.replace('{t}', str(transaction))
            descricao = readElement(descXpath)
        except:
            day += 1
            transaction = 1
            continue

        valorXpath = paths['Valor lancamento']
        valorXpath = valorXpath.replace('{d}', str(day))
        valorXpath = valorXpath.replace('{t}', str(transaction))
        valor = readElement(valorXpath)

        naviXpath = paths['Link detalhes lancamento']
        naviXpath = naviXpath.replace('{d}', str(day))
        naviXpath = naviXpath.replace('{t}', str(transaction))
        navigateToByClick(naviXpath)

        complementoDesc = readElement(paths['Detalhes - comp.desc'])
        complementoDesc = complementoDesc.strip()

        dataCompra = readElement(paths['Detalhes - hora'])
        if '·' in dataCompra:
            dataCompra = dataCompra.replace(' · ', ' ')
            dataCompra = datetime.strptime(dataCompra, "%d/%m/%Y %H:%M:%S")
        else:
            dataCompra = datetime.strptime(dataCompra + " 00:00:00", "%d/%m/%Y %H:%M:%S")

        categoria = readElement(paths['Detalhes - categoria'])
        subcategoria = readElement(paths['Detalhes - subcategoria'])
        banco = readElement(paths['Detalhes - banco'])
        navigateToByClick(paths['Detalhes - voltar'])

        row_id = descricao.replace(' ', '') + "_" + valor.replace(',', '') + "_" + datetime.strftime(dataCompra,
                                                                                                     "%Y%m%d%H%M%S")

        new_row = pd.DataFrame({'ID': row_id,
                                'DescricaoBanco': descricao,
                                'ComplementoDescricao': complementoDesc,
                                'Valor': valor,
                                'DataCompra': dataCompra,
                                'DataLancamento': dataCompra,
                                'Banco': banco,
                                'TipoLancamento': 'Debito',
                                'Parcela': "0",
                                'Parcelas': "0",
                                'Categoria': categoria,
                                'Subcategoria': subcategoria
                                }, index=[0])
        df = pd.concat([df, new_row])

        print("Row added: " + new_row.loc[0, 'ID'])

        # print("diaMes= "+diaMes+"\ndescricao= "+descricao+"\nvalor: "+valor+"\ndataCompra= "+dataCompra+"\ncategoria= "+categoria+"\nsubcategoria= "+subcategoria+"\nbanco= "+banco)
        # print("\n\n")
        transaction += 1

    return df.reset_index(drop=True)

    # Drive Functions


def readBase():
    gc = gspread.service_account(filename="C:\_Dev\BB\service_account.json")
    sh = gc.open("Carteira RPA")
    worksheet = sh.worksheet("BaseHistorica")
    base_dict = worksheet.get_all_records()
    return pd.DataFrame.from_dict(base_dict)


def driveAuthorize():
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]

    credentials = Credentials.from_service_account_file(
        "C:\_Dev\BB\service_account.json",
        scopes=scopes
    )

    gspread.authorize(credentials)


# Actions

if __name__ == '__main__':
    xpathsFilepath = "C:\_Dev\BB\docs\BBPortalXpaths.json"
    xpaths = readXpaths(xpathsFilepath)
    driveAuthorize()
    dfBase = readBase()
    loginBB()
    accessMultiStatement(xpaths)
    dfTransactions = readTransactions(xpaths)


    """
    driver.find_element(By.XPATH, "//*[@id='acheFacil']").send_keys(SEARCH_STRING)
    time.sleep(1)
    driver.find_element(By.XPATH, "//*[@id='listaAcheFacil']/ul/li/a").click()
    time.sleep(1)
    wait_10s.until(expected_conditions.presence_of_element_located((By.XPATH, "//*[@id='carousel-cartoes']/img[1]")))
    driver.find_element(By.XPATH, "//*[@id='carousel-cartoes']/img[1]").click()
    time.sleep(1)
    wait_10s.until(expected_conditions.presence_of_element_located((By.XPATH, "//*[@id='faturasAtual']/li[12]/a")))
    driver.find_element(By.XPATH, "//*[@id='faturasAtual']/li[12]/a").click()
    time.sleep(1)
    driver.find_element(By.XPATH, "//*[@id='toolbarCartao']/li[5]/a").click()
    time.sleep(1)
    driver.find_element(By.XPATH, "/html/body/div[4]/div[2]/ul/li[2]/a").click()
    time.sleep(1)
    driver.find_element(By.XPATH, "/html/body/div[2]/div/div[1]/ul/li/ul/li[3]/ul/li[4]/a").click()
    time.sleep(1)
    driver.close()
    """
