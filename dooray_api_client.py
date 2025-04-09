import requests

class DoorayAPIClient:
    def __init__(self, token: str, base_url: str = "https://api.dooray.co.kr"):
        self.token = token
        self.base_url = base_url

        self.headers = {
            "Authorization": f"dooray-api {self.token}"
        }
    def _request(self, method: str, endpoint: str, params=None, data=None, json_data=None, files=None, extra_headers=None):
        url = self.base_url + endpoint
        headers = self.headers.copy()
        if extra_headers:
            headers.update(extra_headers)

        response = requests.request(method, url, params=params, data=data, json=json_data, files=files, headers=headers)
        response.raise_for_status()
        return response.json()

    def _post_file_with_redirect(self, url: str, params: dict, file_field: str, file_path: str, data: dict = None, extra_headers: dict = None):
        headers = self.headers.copy()
        if extra_headers:
            headers.update(extra_headers)
        with open(file_path, "rb") as f:
            files = {file_field: f}
            # 자동 리디렉션을 비활성화하여 첫 요청을 보냄
            response = requests.post(url, params=params, data=data, files=files, headers=headers, allow_redirects=False)

        if response.status_code == 307:
            location = response.headers.get("location")
            if not location:
                raise Exception("307 응답이지만 location 헤더가 없습니다.")
            with open(file_path, "rb") as f:
                files = {file_field: f}
                response = requests.post(location, params=params, data=data, files=files, headers=headers)

        response.raise_for_status()
        return response.json()

    def _put_file_with_redirect(self, url: str, params: dict, file_field: str, file_path: str, data: dict = None, extra_headers: dict = None):
        """
        PUT 방식 파일 업로드(업데이트) 시 307 응답을 처리하는 헬퍼 메서드.
        """
        headers = self.headers.copy()
        if extra_headers:
            headers.update(extra_headers)

        with open(file_path, "rb") as f:
            files = {file_field: f}
            response = requests.put(url, params=params, data=data, files=files, headers=headers, allow_redirects=False)

        if response.status_code == 307:
            location = response.headers.get("location")
            if not location:
                raise Exception("307 응답이지만 location 헤더가 없습니다.")
            with open(file_path, "rb") as f:
                files = {file_field: f}
                response = requests.put(location, params=params, data=data, files=files, headers=headers)

        response.raise_for_status()
        return response.json()

    def get_members(self, externalEmailAddresses: str, name: str = None, userCode: str = None,
                    userCodeExact: str = None, idProviderUserId: str = None, page: int = 0, size: int = 20):
        endpoint = "/common/v1/members"
        params = {
            "externalEmailAddresses": externalEmailAddresses,
            "page": page,
            "size": size
        }
        if name:
            params["name"] = name
        if userCode:
            params["userCode"] = userCode
        if userCodeExact:
            params["userCodeExact"] = userCodeExact
        if idProviderUserId:
            params["idProviderUserId"] = idProviderUserId
        return self._request("GET", endpoint, params=params)

    # ==================== 드라이브 API ====================
    def get_drives(self, projectId: str = None, type: str = "private", scope: str = None, state: str = "active"):
        endpoint = "/drive/v1/drives"
        params = {"type": type, "state": state}
        if projectId:
            params["projectId"] = projectId
        if scope:
            params["scope"] = scope
        return self._request("GET", endpoint, params=params)

    def get_drive(self, drive_id: str):
        endpoint = f"/drive/v1/drives/{drive_id}"
        return self._request("GET", endpoint)

    def upload_file(self, drive_id: str, parent_id: str, file_path: str):
        """
        파일 업로드 (드라이브에 단일 파일 업로드)
        """
        upload_url = f"https://api.dooray.co.kr/drive/v1/drives/{drive_id}/files"
        params = {"parentId": parent_id}
        headers = {"Authorization": f"dooray-api {self.token}"}
        return self._post_file_with_redirect(upload_url, params, file_field="file", file_path=file_path, data=None, extra_headers=headers)

    def get_files(self, drive_id: str, type: str = None, subTypes: str = None, parentId: str = None, page: int = 0, size: int = 20):
        endpoint = f"/drive/v1/drives/{drive_id}/files"
        params = {"page": page, "size": size}
        if type:
            params["type"] = type
        if subTypes:
            params["subTypes"] = subTypes
        if parentId:
            params["parentId"] = parentId
        return self._request("GET", endpoint, params=params)

    def get_file_meta(self, drive_id: str, file_id: str):
        endpoint = f"/drive/v1/drives/{drive_id}/files/{file_id}"
        params = {"media": "meta"}
        return self._request("GET", endpoint, params=params)

    def download_file(self, drive_id: str, file_id: str, save_path: str):
        """
        파일 다운로드 시에도 307 응답을 확인하여 재요청합니다.
        """
        download_url = f"https://api.dooray.co.kr/drive/v1/drives/{drive_id}/files/{file_id}"
        params = {"media": "raw"}
        headers = {"Authorization": f"dooray-api {self.token}"}
        # 자동 리디렉션 비활성화
        response = requests.get(download_url, params=params, headers=headers, stream=True, allow_redirects=False)
        if response.status_code == 307:
            location = response.headers.get("location")
            if not location:
                raise Exception("307 응답이지만 location 헤더가 없습니다.")
            response = requests.get(location, params=params, headers=headers, stream=True)
        response.raise_for_status()
        with open(save_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return f"파일이 {save_path}에 저장되었습니다."

    def update_file_name(self, drive_id: str, file_id: str, new_name: str):
        endpoint = f"/drive/v1/drives/{drive_id}/files/{file_id}"
        params = {"media": "meta"}
        json_data = {"name": new_name}
        headers = {"Content-Type": "application/json"}
        return self._request("PUT", endpoint, params=params, json_data=json_data, extra_headers=headers)

    def update_file_version(self, drive_id: str, file_id: str, file_path: str):
        """
        파일 업데이트 (새 버전 업로드) 시 PUT 방식의 307 리디렉션을 처리합니다.
        """
        update_url = f"https://api.dooray.co.kr/drive/v1/drives/{drive_id}/files/{file_id}"
        params = {"media": "raw"}
        headers = {"Authorization": f"dooray-api {self.token}"}
        return self._put_file_with_redirect(update_url, params, file_field="file", file_path=file_path, data=None, extra_headers=headers)

    def delete_file(self, drive_id: str, file_id: str):
        endpoint = f"/drive/v1/drives/{drive_id}/files/{file_id}"
        return self._request("DELETE", endpoint)

    def create_folder(self, drive_id: str, folder_id: str, folder_name: str):
        endpoint = f"/drive/v1/drives/{drive_id}/files/{folder_id}/create-folder"
        json_data = {"name": folder_name}
        headers = {"Content-Type": "application/json"}
        return self._request("POST", endpoint, json_data=json_data, extra_headers=headers)

    def copy_file(self, drive_id: str, file_id: str, destination_drive_id: str, destination_file_id: str):
        endpoint = f"/drive/v1/drives/{drive_id}/files/{file_id}/copy"
        json_data = {
            "destinationDriveId": destination_drive_id,
            "destinationFileId": destination_file_id
        }
        headers = {"Content-Type": "application/json"}
        return self._request("POST", endpoint, json_data=json_data, extra_headers=headers)

    def move_file(self, drive_id: str, file_id: str, destination_file_id: str):
        endpoint = f"/drive/v1/drives/{drive_id}/files/{file_id}/move"
        json_data = {"destinationFileId": destination_file_id}
        headers = {"Content-Type": "application/json"}
        return self._request("POST", endpoint, json_data=json_data, extra_headers=headers)

    # ============ Shared Links (파일 공유링크) ============

    def create_shared_link(self, drive_id: str, file_id: str, scope: str, expiredAt: str):
        endpoint = f"/drive/v1/drives/{drive_id}/files/{file_id}/shared-links"
        json_data = {"scope": scope, "expiredAt": expiredAt}
        headers = {"Content-Type": "application/json"}
        return self._request("POST", endpoint, json_data=json_data, extra_headers=headers)

    def get_shared_links(self, drive_id: str, file_id: str, valid: bool = True):
        endpoint = f"/drive/v1/drives/{drive_id}/files/{file_id}/shared-links"
        params = {"valid": str(valid).lower()}
        return self._request("GET", endpoint, params=params)

    def get_shared_link(self, drive_id: str, file_id: str, link_id: str):
        endpoint = f"/drive/v1/drives/{drive_id}/files/{file_id}/shared-links/shared-links/{link_id}"
        return self._request("GET", endpoint)

    def update_shared_link(self, drive_id: str, file_id: str, link_id: str, expiredAt: str, scope: str):
        endpoint = f"/drive/v1/drives/{drive_id}/files/{file_id}/shared-links/shared-links/{link_id}"
        json_data = {"expiredAt": expiredAt, "scope": scope}
        headers = {"Content-Type": "application/json"}
        return self._request("PUT", endpoint, json_data=json_data, extra_headers=headers)

    def delete_shared_link(self, drive_id: str, file_id: str, link_id: str):
        endpoint = f"/drive/v1/drives/{drive_id}/files/{file_id}/shared-links/shared-links/{link_id}"
        return self._request("DELETE", endpoint)

    # ==================== 위키 API ====================
    def get_wikis(self, page: int = 0, size: int = 20):
        endpoint = "/wiki/v1/wikis"
        params = {"page": page, "size": size}
        return self._request("GET", endpoint, params=params)

    def create_wiki_page(self, wiki_id: str, parentPageId: str, subject: str, content: str, attachFileIds: list = None, referrers: list = None):
        endpoint = f"/wiki/v1/wikis/{wiki_id}/pages"
        json_data = {
            "parentPageId": parentPageId,
            "subject": subject,
            "body": {
                "mimeType": "text/x-markdown",
                "content": content
            }
        }
        if attachFileIds:
            json_data["attachFileIds"] = attachFileIds
        if referrers:
            json_data["referrers"] = referrers
        headers = {"Content-Type": "application/json"}
        return self._request("POST", endpoint, json_data=json_data, extra_headers=headers)

    def get_wiki_pages(self, wiki_id: str, parentPageId: str = None):
        endpoint = f"/wiki/v1/wikis/{wiki_id}/pages"
        params = {}
        if parentPageId is not None:
            params["parentPageId"] = parentPageId
        return self._request("GET", endpoint, params=params)

    def get_wiki_page(self, wiki_id: str, page_id: str):
        endpoint = f"/wiki/v1/wikis/{wiki_id}/pages/{page_id}"
        return self._request("GET", endpoint)

    def update_wiki_page(self, wiki_id: str, page_id: str, subject: str, content: str, referrers: list = None):
        endpoint = f"/wiki/v1/wikis/{wiki_id}/pages/{page_id}"
        json_data = {
            "subject": subject,
            "body": {
                "mimeType": "text/x-markdown",
                "content": content
            }
        }
        if referrers is not None:
            json_data["referrers"] = referrers
        headers = {"Content-Type": "application/json"}
        return self._request("PUT", endpoint, json_data=json_data, extra_headers=headers)

    def update_wiki_page_title(self, wiki_id: str, page_id: str, subject: str):
        endpoint = f"/wiki/v1/wikis/{wiki_id}/pages/{page_id}/title"
        json_data = {"subject": subject}
        headers = {"Content-Type": "application/json"}
        return self._request("PUT", endpoint, json_data=json_data, extra_headers=headers)

    def update_wiki_page_content(self, wiki_id: str, page_id: str, content: str):
        endpoint = f"/wiki/v1/wikis/{wiki_id}/pages/{page_id}/content"
        json_data = {"body": {"mimeType": "text/x-markdown", "content": content}}
        headers = {"Content-Type": "application/json"}
        return self._request("PUT", endpoint, json_data=json_data, extra_headers=headers)

    def update_wiki_page_referrers(self, wiki_id: str, page_id: str, referrers: list):
        endpoint = f"/wiki/v1/wikis/{wiki_id}/pages/{page_id}/referrers"
        json_data = {"referrers": referrers}
        headers = {"Content-Type": "application/json"}
        return self._request("PUT", endpoint, json_data=json_data, extra_headers=headers)

    def create_wiki_comment(self, wiki_id: str, page_id: str, content: str):
        endpoint = f"/wiki/v1/wikis/{wiki_id}/pages/{page_id}/comments"
        json_data = {"body": {"content": content}}
        headers = {"Content-Type": "application/json"}
        return self._request("POST", endpoint, json_data=json_data, extra_headers=headers)

    def get_wiki_comments(self, wiki_id: str, page_id: str, page: int = 0, size: int = 20):
        endpoint = f"/wiki/v1/wikis/{wiki_id}/pages/{page_id}/comments"
        params = {"page": page, "size": size}
        return self._request("GET", endpoint, params=params)

    def get_wiki_comment(self, wiki_id: str, page_id: str, comment_id: str):
        endpoint = f"/wiki/v1/wikis/{wiki_id}/pages/{page_id}/comments/{comment_id}"
        return self._request("GET", endpoint)

    def update_wiki_comment(self, wiki_id: str, page_id: str, comment_id: str, content: str):
        endpoint = f"/wiki/v1/wikis/{wiki_id}/pages/{page_id}/comments/{comment_id}"
        json_data = {"body": {"content": content}}
        headers = {"Content-Type": "application/json"}
        return self._request("PUT", endpoint, json_data=json_data, extra_headers=headers)

    def delete_wiki_comment(self, wiki_id: str, page_id: str, comment_id: str):
        endpoint = f"/wiki/v1/wikis/{wiki_id}/pages/{page_id}/comments/{comment_id}"
        return self._request("DELETE", endpoint)

    def upload_wiki_page_file(self, wiki_id: str, page_id: str, file_path: str, file_type: str = "general"):
        """
        위키 페이지에 파일 업로드 시 307 응답을 처리합니다.
        """
        url = f"{self.base_url}/wiki/v1/wikis/{wiki_id}/pages/{page_id}/files"
        data = {"type": file_type}
        headers = {"Authorization": f"dooray-api {self.token}"}
        return self._post_file_with_redirect(url, params={}, file_field="file", file_path=file_path, data=data, extra_headers=headers)

    def upload_wiki_file(self, wiki_id: str, file_path: str, file_type: str = "general"):
        """
        위키에 파일 업로드 시 307 응답을 처리합니다.
        """
        url = f"{self.base_url}/wiki/v1/wikis/{wiki_id}/files"
        data = {"type": file_type}
        headers = {"Authorization": f"dooray-api {self.token}"}
        return self._post_file_with_redirect(url, params={}, file_field="file", file_path=file_path, data=data, extra_headers=headers)