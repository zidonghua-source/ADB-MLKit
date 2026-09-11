"""Replace the example XPath with a selector for your app's UI."""
from adb_mlkit import ADBMLKit


def main():
    client = ADBMLKit()
    result = client.recognize_xpath('//*[@resource-id="com.example:id/dialog"]/..', language="vi")
    print(result.text)
    print(result.image)


if __name__ == "__main__":
    main()
