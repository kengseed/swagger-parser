import csv
import os
import json
import yaml


def read_swagger_file(file_content, file_type):
    if file_type == "json":
        return json.loads(file_content)
    if file_type in ["yaml", "yml"]:
        return yaml.safe_load(file_content)

    raise ValueError("Unsupported file format. Only JSON and YAML are supported.")


def join_array(list, separator):
    if len(list) > 0:
        return str(separator).join(list)
    else:
        return ""


def get_enum_properties(swagger_data, schema_name):
    schema = swagger_data.get("components", {}).get("schemas", {}).get(schema_name, {})
    if len(schema.get("enum", [])) > 0:
        return schema
    else:
        return []


def get_model_ref(obj, is_array):
    return obj.get("items", {}).get("$ref", "") if is_array else obj.get("$ref", "")


def get_object_name(sub_schema_name, prop_name, is_array):
    return (
        ((sub_schema_name + ".") if sub_schema_name != "" else "")
        + prop_name
        + ("[]" if is_array else "")
    )


def get_properties_by_schema(
    swagger_data,
    schema_name,
    prop_results,
    sub_schema_name,
    isRequestBody,
    isResponseBody,
    oneOfSchema,
):
    # prop_results = prevProperties if len(prevProperties) > 0 else []

    # Get schema details
    schema = (
        oneOfSchema
        if oneOfSchema is not None
        else swagger_data.get("components", {}).get("schemas", {}).get(schema_name, {})
    )
    properties = schema.get("properties", {})
    requiredFields = schema.get("required", [])

    for prop_name, prop in properties.items():
        # Check array type
        ref = get_model_ref(prop, False)
        array_schema_name = str(ref).replace("#/components/schemas/", "")
        array_schema = (
            swagger_data.get("components", {})
            .get("schemas", {})
            .get(array_schema_name, {})
        )
        is_array_prop_level = (
            prop.get("type") == "array" or array_schema.get("type") == "array"
        )

        # Get property by reference object
        prop_ref = array_schema if array_schema.get("type") == "array" else prop
        ref = get_model_ref(prop_ref, is_array_prop_level)
        object_name = get_object_name(sub_schema_name, prop_name, is_array_prop_level)

        # If refer to model (Supported Enum, Object, Array)
        if ref != "":
            sub_schema = str(ref).replace("#/components/schemas/", "")
            enum_properties = get_enum_properties(swagger_data, sub_schema)

            if len(enum_properties) > 0:  # Enum
                if (not isRequestBody or not enum_properties.get("readOnly", "")) and (
                    not isResponseBody or not enum_properties.get("writeOnly", "")
                ):
                    prop_results.append(
                        {
                            "subDomain": schema_name,
                            "fieldName": object_name,
                            "fieldDescription": enum_properties.get("description"),
                            "fieldDataType": enum_properties.get("type"),
                            "required": prop_name in requiredFields,
                            "fieldFormat": enum_properties.get("format", ""),
                            "fieldExampleValue": "'"
                            + str(enum_properties.get("example", "")),
                            "fieldIsReadOnly": enum_properties.get("readOnly", ""),
                            "fieldIsWriteOnly": enum_properties.get("writeOnly", ""),
                            "fieldValuePattern": enum_properties.get("pattern", ""),
                            "fieldMinLength": enum_properties.get("minLength", ""),
                            "fieldMaxLength": enum_properties.get("maxLength", ""),
                            "enumListValue": join_array(
                                enum_properties.get("enum", []), ","
                            ),
                        }
                    )
            else:  # Object, Array
                if (not isRequestBody or not prop.get("readOnly", "")) and (
                    not isResponseBody or not prop.get("writeOnly", "")
                ):
                    prop_results.append(
                        {
                            "subDomain": schema_name,
                            "fieldName": object_name,
                            "fieldDescription": prop.get("description"),
                            "fieldDataType": prop.get("type", ""),
                            "required": prop_name in requiredFields,
                            "fieldFormat": "",
                            "fieldExampleValue": "",
                            "fieldIsReadOnly": prop.get("readOnly", ""),
                            "fieldIsWriteOnly": prop.get("writeOnly", ""),
                            "fieldValuePattern": "",
                            "fieldMinLength": "",
                            "fieldMaxLength": "",
                            "enumListValue": "",
                        }
                    )

                    get_properties_by_schema(
                        swagger_data,
                        sub_schema,
                        prop_results,
                        object_name,
                        isRequestBody,
                        isResponseBody,
                        None,
                    )
        else:
            if (not isRequestBody or not prop.get("readOnly", "")) and (
                not isResponseBody or not prop.get("writeOnly", "")
            ):
                # Check is oneOf array
                oneOfProperties = prop.get("oneOf", [])

                prop_results.append(
                    {
                        "subDomain": schema_name,
                        "fieldName": object_name,
                        "fieldDescription": prop.get("description"),
                        "fieldDataType": (
                            "One of " + str(prop.get("type"))
                            if len(oneOfProperties) > 0
                            else prop.get("type")
                        ),
                        "required": prop_name in requiredFields,
                        "fieldFormat": prop.get("format", ""),
                        "fieldExampleValue": "'" + str(prop.get("example", "")),
                        "fieldIsReadOnly": prop.get("readOnly", ""),
                        "fieldIsWriteOnly": prop.get("writeOnly", ""),
                        "fieldValuePattern": prop.get("pattern", ""),
                        "fieldMinLength": prop.get("minLength", ""),
                        "fieldMaxLength": prop.get("maxLength", ""),
                        "enumListValue": join_array(prop.get("enum", []), ","),
                    }
                )

                if len(oneOfProperties) > 0:
                    for oneOfProp in oneOfProperties:
                        get_properties_by_schema(
                            swagger_data,
                            schema_name,
                            prop_results,
                            object_name,
                            isRequestBody,
                            isResponseBody,
                            oneOfProp,
                        )
    return prop_results


def extract_schemas(swagger_data):
    schemas = swagger_data.get("components", {}).get("schemas", {})
    parsed_data = []

    for schema_name, schema in schemas.items():
        properties = schema.get("properties", {})
        required = schema.get("required", [])

        for prop_name, prop in properties.items():
            enum = prop.get("enum", [])
            modelArrayRef = prop.get("items", {}).get("$ref", "")

            item = {
                "schema name": schema_name,
                "properties name": prop_name,
                "type": prop.get("type"),
                "format": prop.get("format"),
                "description": prop.get("description"),
                "example": "'" + str(prop.get("example")),
                "required": prop_name in required,
                "enum": ", ".join(enum) if enum else "",
                "modelRef": prop.get("$ref"),
                "modelArrayRef": modelArrayRef,
            }
            parsed_data.append(item)
    return parsed_data


def extract_services_with_properties(swagger_data):
    parsed_data = []

    for path, methods in swagger_data.get("paths", {}).items():
        for method, details in methods.items():
            # Get data to variables
            requestBodyRef = (
                details.get("requestBody", {})
                .get("content", {})
                .get("application/json", {})
                .get("schema", {})
                .get("$ref", "")
            )
            responseBodyRef = (
                details.get("responses", {})
                .get("200", {})
                .get("content", {})
                .get("application/json", {})
                .get("schema", {})
                .get("$ref", "")
            )
            responseCodes = (", ").join(
                [str(code) for code in details.get("responses", {}).keys()]
            )

            # Add Parameters Detail (Header, Path, Query)
            for param in details.get("parameters", []):

                item = {
                    "tag": details.get("tags", "")[0],
                    "operationId": details.get("operationId", ""),
                    "path": path,
                    "method": method.upper(),
                    "summary": details.get("summary", ""),
                    "description": details.get("description", ""),
                    "fieldType": param.get("in", ""),
                    "subDomain": "",
                    "fieldName": param.get("name", ""),
                    "fieldDescription": param.get("description", ""),
                    "fieldDataType": param.get("schema", "").get("type", ""),
                    "required": param.get("required", ""),
                    "fieldFormat": param.get("schema", "").get("format", ""),
                    "fieldExampleValue": "'" + str(param.get("example", "")),
                    "fieldIsReadOnly": param.get("schema", "").get("readOnly", ""),
                    "fieldIsWriteOnly": param.get("schema", "").get("writeOnly", ""),
                    "fieldValuePattern": param.get("schema", "").get("pattern", ""),
                    "fieldMinLength": param.get("schema", "").get("minLength", ""),
                    "fieldMaxLength": param.get("schema", "").get("maxLength", ""),
                    "enumListValue": join_array(param.get("enum", []), ","),
                    "responses": responseCodes,
                }
                parsed_data.append(item)

            # Add Request Body Details (If have model ref)
            if requestBodyRef != "":
                properties = get_properties_by_schema(
                    swagger_data,
                    str(requestBodyRef).replace("#/components/schemas/", ""),
                    [],
                    "",
                    True,
                    False,
                    None,
                )

                for prop in properties:
                    item = {
                        "tag": details.get("tags", "")[0],
                        "operationId": details.get("operationId", ""),
                        "path": path,
                        "method": method.upper(),
                        "summary": details.get("summary", ""),
                        "description": details.get("description", ""),
                        "fieldType": "requestBody",
                        "subDomain": prop["subDomain"],
                        "fieldName": prop["fieldName"],
                        "fieldDescription": prop["fieldDescription"],
                        "fieldDataType": prop["fieldDataType"],
                        "required": prop["required"],
                        "fieldFormat": prop["fieldFormat"],
                        "fieldExampleValue": "'" + str(prop["fieldExampleValue"]),
                        "fieldIsReadOnly": prop["fieldIsReadOnly"],
                        "fieldIsWriteOnly": prop["fieldIsWriteOnly"],
                        "fieldValuePattern": prop["fieldValuePattern"],
                        "fieldMinLength": prop["fieldMinLength"],
                        "fieldMaxLength": prop["fieldMaxLength"],
                        "enumListValue": prop["enumListValue"],
                        "responses": responseCodes,
                    }
                    parsed_data.append(item)

            # Add Response Body Details (If have model ref)
            if responseBodyRef != "":
                properties = get_properties_by_schema(
                    swagger_data,
                    str(responseBodyRef).replace("#/components/schemas/", ""),
                    [],
                    "",
                    False,
                    True,
                    None,
                )

                for prop in properties:
                    item = {
                        "tag": details.get("tags", "")[0],
                        "operationId": details.get("operationId", ""),
                        "path": path,
                        "method": method.upper(),
                        "summary": details.get("summary", ""),
                        "description": details.get("description", ""),
                        "fieldType": "responseBody",
                        "subDomain": prop["subDomain"],
                        "fieldName": prop["fieldName"],
                        "fieldDescription": prop["fieldDescription"],
                        "fieldDataType": prop["fieldDataType"],
                        "required": prop["required"],
                        "fieldFormat": prop["fieldFormat"],
                        "fieldExampleValue": "'" + str(prop["fieldExampleValue"]),
                        "fieldIsReadOnly": prop["fieldIsReadOnly"],
                        "fieldIsWriteOnly": prop["fieldIsWriteOnly"],
                        "fieldValuePattern": prop["fieldValuePattern"],
                        "fieldMinLength": prop["fieldMinLength"],
                        "fieldMaxLength": prop["fieldMaxLength"],
                        "enumListValue": prop["enumListValue"],
                        "responses": responseCodes,
                    }
                    parsed_data.append(item)

    return parsed_data


def extract_schemas_with_properties(swagger_data):
    parsed_data = []

    for schema_name, schema in (
        swagger_data.get("components", {}).get("schemas", {}).items()
    ):
        properties = get_properties_by_schema(
            swagger_data,
            schema_name,
            [],
            "",
            False,
            False,
            None,
        )

        for prop in properties:
            item = {
                "subDomain": schema_name,
                "fieldName": prop["fieldName"],
                "fieldDescription": prop["fieldDescription"],
                "fieldDataType": prop["fieldDataType"],
                "required": prop["required"],
                "fieldFormat": prop["fieldFormat"],
                "fieldExampleValue": "'" + str(prop["fieldExampleValue"]),
                "fieldIsReadOnly": prop["fieldIsReadOnly"],
                "fieldIsWriteOnly": prop["fieldIsWriteOnly"],
                "fieldValuePattern": prop["fieldValuePattern"],
                "fieldMinLength": prop["fieldMinLength"],
                "fieldMaxLength": prop["fieldMaxLength"],
                "enumListValue": prop["enumListValue"],
            }
            parsed_data.append(item)

    return parsed_data


def write_schema_to_csv(data, output_file):
    file_name = output_file + "_schemas_output.csv"

    with open(file_name, "w", newline="", encoding="utf-8") as file:
        # Layout for extract_schemas function
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "schema name",
                "properties name",
                "type",
                "format",
                "description",
                "example",
                "required",
                "enum",
                "modelRef",
                "modelArrayRef",
            ],
        )

        writer.writeheader()
        writer.writerows(data)

    return file_name


def write_services_with_properties_to_csv(data, output_file):
    file_name = output_file + "_services_output.csv"

    with open(file_name, "w", newline="", encoding="utf-8") as file:
        # Layout for parse swagger function
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "tag",
                "operationId",
                "path",
                "method",
                "summary",
                "description",
                "fieldType",
                "subDomain",
                "fieldName",
                "fieldDescription",
                "fieldDataType",
                "required",
                "fieldFormat",
                "fieldExampleValue",
                "fieldIsReadOnly",
                "fieldIsWriteOnly",
                "fieldValuePattern",
                "fieldMinLength",
                "fieldMaxLength",
                "enumListValue",
                "responses",
            ],
        )

        writer.writeheader()
        writer.writerows(data)

    return file_name


def write_schema_with_properties_to_csv(data, output_file):
    file_name = output_file + "_schemas_output.csv"

    with open(file_name, "w", newline="", encoding="utf-8") as file:
        # Layout for extract_schemas function
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "subDomain",
                "fieldName",
                "fieldDescription",
                "fieldDataType",
                "required",
                "fieldFormat",
                "fieldExampleValue",
                "fieldIsReadOnly",
                "fieldIsWriteOnly",
                "fieldValuePattern",
                "fieldMinLength",
                "fieldMaxLength",
                "enumListValue",
            ],
        )

        writer.writeheader()
        writer.writerows(data)

    return file_name


def process_swagger_file(file_content, file_type, output_file):
    output_file_names = []

    swagger_data = read_swagger_file(file_content, file_type)

    parsed_data = extract_services_with_properties(swagger_data)
    output_file_names.append(
        write_services_with_properties_to_csv(parsed_data, output_file)
    )

    parsed_data = extract_schemas_with_properties(swagger_data)
    output_file_names.append(
        write_schema_with_properties_to_csv(parsed_data, output_file)
    )

    return output_file_names
