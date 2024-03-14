import json
import time
import re
import argparse
import pandas as pd
from scraper import AbstractPropertyScraper


class NinetyNineCoScraper(AbstractPropertyScraper):
    DISTRICTS = {
        "01": "Boat Quay / Raffles Place / Marina",
        "02": "Chinatown / Tanjong Pagar",
        "03": "Alexandra / Commonwealth",
        "04": "Harbourfront / Telok Blangah",
        "05": "Buona Vista / West Coast / Clementi",
        "06": "City Hall / Clarke Quay",
        "07": "Beach Road / Bugis / Rochor",
        "08": "Farrer Park / Serangoon Rd",
        "09": "Orchard / River Valley",
        "10": "Tanglin / Holland",
        "11": "Newton / Novena",
        "12": "Balestier / Toa Payoh",
        "13": "Macpherson / Potong Pasir",
        "14": "Eunos / Geylang / Paya Lebar",
        "15": "East Coast / Marine Parade",
        "16": "Bedok / Upper East Coast",
        "17": "Changi Airport / Changi Village",
        "18": "Pasir Ris / Tampines",
        "19": "Hougang / Punggol / Sengkang",
        "20": "Ang Mo Kio / Bishan / Thomson",
        "21": "Clementi Park / Upper Bukit Timah",
        "22": "Boon Lay / Jurong / Tuas",
        "23": "Bukit Batok / Bukit Panjang / Choa Chu Kang",
        "24": "Lim Chu Kang / Tengah",
        "25": "Admiralty / Woodlands",
        "26": "Mandai / Upper Thomson",
        "27": "Sembawang / Yishun",
        "28": "Seletar / Yio Chu Kang"
    }

    def __init__(self,
                 header='https://www.99.co',
                 key='/singapore/rent',
                 query='?query_ids=dtdistrict{district}&query_type=district&rental_type=all',
                 ):
        super().__init__(header, key, query)
        self.platform_name = '99.co'
        self.pages_to_fetch = 20
        self.properties_per_page = 200
        self.pagination_element = "ul.SearchPagination-links"
        self.rental_prices_dir = f'./rental_prices/ninety_nine/'

    def pagination(self, soup):
        pagination = soup.select_one(self.pagination_element)
        try:
            # only 1 page
            if pagination.find_all("li", class_="next disabled"):
                pages = int(pagination.find_all("a")[1].text)
            # grab the page number before the arrow
            else:
                pages = int(pagination.find_all("a")[-2].text)
        except AttributeError:
            # TODO: check if this is the correct way to handle this
            if soup.find("h2", class_="name").text.split(' ')[2] == '0':
                print('No property found. Scraping stopped.')
            exit(1)
        return pages

    def link_scraper(self, soup):
        links = []
        units = soup.find_all("div", class_="_2J3pS")
        for unit in units:
            prop = unit.find("a", itemprop='url')
            prop_name = prop['title'].strip()
            links.append((prop_name, prop["href"]))
        return links

    def get_prop_info(self, soup):
        output = {col_name: None for col_name in self.COLUMNS}

        try:
            output["price"] = soup.find(
                'div', id='price').find('p').text.strip()
        except Exception as err:
            print(f"Error scraping price: {err}")
            return {}

        try:
            beds_element = soup.find('img', {'alt': 'Beds'})
            beds = beds_element.find_next_sibling().text if beds_element else None

            baths_element = soup.find('img', {'alt': 'Bath'})
            baths = baths_element.find_next_sibling().text if baths_element else None

            floor_area_element = soup.find('img', {'alt': 'Floor Area'})
            floor_area = floor_area_element.find_next_sibling(
            ).text if floor_area_element else None

            output['bedroom'] = beds
            output['bathroom'] = baths
            output['dimensions'] = floor_area
        except Exception as err:
            print(f"Error scraping (bed,bath,sqft) info: {err}")

        try:
            address_span = soup.find('p', class_="dniCg _3j72o _2rhE-")
            address = address_span.text.strip().split('\n')[0]
            """ 
            e.g "· Executive Condo for Rent\nAdmiralty / Woodlands (D25)"
            -> Starts with "·" = no address
            -> remove everything after the first "·" until "Rent" and strip whitespace
            """
            if address.startswith('·'):
                raise Exception('Address not found')
            pattern = re.compile(r'\s·.*?Rent', re.DOTALL)
            address = re.sub(pattern, '', address)
            output['address'] = address.strip()
        except Exception as err:
            print(f"Error scraping address: {err}")

        try:
            # Find the script tag by ID
            script_tag = soup.find('script', {'id': '__REDUX_STORE__'})

            pattern = re.compile(
                r'"coordinates":\{"lng":([0-9.-]+),"lat":([0-9.-]+)\}')
            match = pattern.search(script_tag.text.strip())

            if match:
                # Extract the matched JSON string
                json_string = "{" + match.group() + "}"

                # Load the JSON content
                json_data = json.loads(json_string)

                # Access lat and lng values
                lat = json_data.get('coordinates', {}).get('lat')
                lng = json_data.get('coordinates', {}).get('lng')

                output['latitude'] = lat
                output['longitude'] = lng
        except Exception as err:
            print(f"Error scraping coordinates: {err}")

        try:
            # Extract the nearest MRT station and distance
            mrt_info = soup.find(
                'p', class_='_2sIc2 _2rhE- _1c-pJ').text.strip()
            # e.g: 3 mins (175 m) from Shenton Way MRT
            distance, output['nearest_mrt'] = mrt_info.split(' from ')

            distance_match = re.search(r'\((\d+)\s*m\)', distance)
            output['distance_to_nearest_mrt'] = distance_match.group(
                1) if distance_match else None
        except Exception as err:
            print(f"Error scraping nearest MRT: {err}")

        try:
            # Extract all facilities
            facilities = soup.find_all('div', class_='_3atmT')
            res = []
            for facility in facilities:
                img_alt = facility.find('img')['alt']
                res.append(img_alt)

            output['facilities'] = res
        except Exception as err:
            print(f"Error scraping facilities: {err}")

        try:
            property_details_rows = soup.select(
                '#propertyDetails table._3NpKo tr._2dry3')

            """ 
            e.g
            Price/sqft: $7.5 psf
            Floor Level: High
            Furnishing: Fully
            Built year: 1976
            Tenure: 99-year leasehold
            Property type: Apartment Whole Unit
            """
            not_included = set(['Last updated'])
            for row in property_details_rows:
                columns = row.find_all('td', class_='NomDX')
                values = row.find_all('td', class_='XCAFU')

                for col, val in zip(columns, values):
                    label = col.get_text(strip=True)
                    if label in not_included:
                        continue

                    output[NinetyNineCoScraper.to_snake_case(
                        label)] = val.get_text(strip=True)
        except Exception as err:
            print(f"Error scraping property details: {err}")

        return output

    def scrape_rental_prices(self, district, debug):
        self.query = self.query.format(district=district)
        print(f"Scraping {self.DISTRICTS[district]}...")

        soup, pages = self.initial_fetch()
        # Scrape links from the first page for rental properties
        self.props += self.link_scraper(soup)
        print('\rPage 1/{} done.'.format(str(pages)))

        # Scrape subsequent pages
        for page in range(2, pages + 1):
            if debug:
                continue

            soup = self.fetch_html(self.header + self.key + '/?page_num=' +
                                   str(page) + self.query, True)
            if not soup:
                print(f'Error fetching page {page}, skipping...')
                continue
            self.props += self.link_scraper(soup)
            print('\rPage {}/{} done.'.format(str(page), str(pages)))

        # Scrape rental info for each property
        rental_infos = []
        print('\nA total of ' + str(min(self.properties_per_page, len(self.props))) +
              ' properties will be scraped.\n')

        for i, prop in enumerate(self.props):
            if debug and i == 6:
                break
            # only scrape self.properties_per_page per district
            if i == self.properties_per_page + 1:
                break
            print(f"Fetching {prop[0]}...")

            url = self.header + prop[1]
            prop_soup = self.fetch_html(url, False)
            rental_info = self.get_prop_info(prop_soup)
            if rental_info == {}:
                continue

            rental_info["property_name"] = prop[0]
            rental_info["district"] = self.DISTRICTS[district]
            rental_info["listing_id"] = url.split('-')[-1]
            rental_info["url"] = url
            rental_infos.append(rental_info)
            print(str(i + 1) + '/' +
                  str(min(self.properties_per_page, len(self.props))) + ' done!')

        df = pd.DataFrame(rental_infos)
        df = df[self.COLUMNS]
        print(df.head())
        self.output_to_csv(df)

        # reset for next run
        self.refresh_variables()

    def refresh_variables(self):
        self.props = []
        self.query = '?query_ids=dtdistrict{district}&query_type=district&rental_type=all'


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--debug", action="store_true",
                        help="Enable debug mode")
    args = parser.parse_args()

    while True:
        try:
            start = time.time()
            ninetynine_co_scraper = NinetyNineCoScraper()
            ninetynine_co_scraper.run(debug=args.debug)
            print(f"\nTime taken: {time.time() - start} seconds")
            break
        except Exception as err:
            print(f'Error scraping: {err}, retrying...')