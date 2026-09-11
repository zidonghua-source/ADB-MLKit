# Third-party components

ADB-MLKit's MIT license covers the integration source written for this repository. It does not relicense external software, pretrained models, platform tooling, or generated wrapper components.

- **Google ML Kit Text Recognition v2**: bundled Latin, Chinese, Devanagari, Japanese and Korean Android libraries, currently pinned in `android/app/build.gradle`. Google's license notices and [ML Kit terms](https://developers.google.com/ml-kit/terms) apply. Model implementation/source is not part of this project.
- **Android SDK / ADB / Android Gradle Plugin**: Google/Android tooling, distributed separately under their applicable terms. Android SDK license acceptance is the builder's responsibility.
- **Gradle wrapper**: generated upstream Gradle wrapper scripts/JAR; Gradle is Apache License 2.0. The wrapper downloads its pinned distribution from the official Gradle service.
- **uiautomator2 and Pillow**: optional Python dependencies for XPath-assisted screenshot capture. Consult their upstream distributions for license details.
- **JUnit**: Android JVM test dependency; consult the dependency's upstream license.

Dependency notices included in artifacts must be preserved. Review the resolved dependency tree and vendor terms before redistributing APKs, especially for commercial use. This file is an inventory, not a substitute for those licenses.
